"""経歴書ドラフト生成タスクの実行サービス（非同期 / ADR-0018）。

worker（``services/tasks``）から呼ばれ、LLM でドラフト payload を生成 → PDF レンダリング検証
→ 課金確定 → ``ResumeDraftCache`` へ保存する。状態遷移・失敗通知は worker が担い、本モジュールは
成功時に ``status="completed"`` + ``result`` を書き戻し、失敗時は ``NonRetryableError`` を raise する。

DB 書き込み（課金・結果保存・状態遷移）は本モジュールと repository に閉じ込める。
``draft_service`` / ``mapper`` / ``context`` の DB 非依存原則（context は SELECT のみ）は維持する。

課金順序の不変条件（同期版 router から移設 / ADR-0012・0018）:
  - LLM/パース失敗時は消費済みトークンを **必ず課金** する（API 原価は発生済み）。
  - PDF レンダリング成功後にのみ本課金を確定する（レンダリング失敗＝課金しない）。
  - 課金記録自体の失敗は ``NonRetryableError`` に包んで dead_letter にする
    （リトライで LLM を再実行＝再課金しないため。「課金漏れ・二重課金を黙って通さない」）。

libSQL (Hrana over HTTP) の idle stream timeout を避けるため、LLM 呼び出しの前後で
セッションを開閉する（run_github_link と同方針）。
"""

from datetime import datetime, timezone

from ....core.logging_utils import get_logger
from ....core.messages import get_error
from ....models import User
from ....repositories.resume_draft import ResumeDraftCacheRepository
from ....services.billing import credit_service
from ....services.pdf.generators.resume_generator import build_resume_pdf
from ...tasks.exceptions import NonRetryableError
from ...tasks.handlers.base import SessionFactory
from ..chat_service import AgentResponseParseError
from ..llm.base import LLMError
from .context import ResumeDraftSourceUnavailableError, build_draft_source
from .draft_service import run_resume_draft

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def run_resume_draft_task(session_factory: SessionFactory, payload: dict) -> None:
    """経歴書ドラフトを生成し、結果をキャッシュに保存する。

    フェーズ構成:
      - A: payload 検証 + 入力取得（SELECT）+ processing マーク（短命セッション）
      - B: LLM 生成 + PDF レンダリング検証（DB セッション無し）
      - C: 課金確定 → 結果書き戻し（新セッション）

    失敗はすべて ``NonRetryableError`` で worker に dead_letter を委ねる
    （LLM/PDF 失敗はリトライで回復せず再課金の恐れがあるため）。
    """
    user_id = payload.get("user_id")
    model = payload.get("model")
    if not user_id or not model:
        message = "経歴書ドラフトタスクのペイロードが不正です"
        logger.error(message, extra={"payload_keys": list(payload.keys())})
        raise NonRetryableError(f"{message} (payload_keys={list(payload.keys())})")

    usage_description = f"経歴書ドラフト生成（{model}）"

    # ── フェーズA: 入力取得 + processing マーク ──────────────────────────────
    with session_factory() as db:
        cache = ResumeDraftCacheRepository(db).get_by_user(user_id)
        if not cache:
            message = "経歴書ドラフトキャッシュが見つかりません"
            logger.error(message, extra={"user_id": user_id})
            raise NonRetryableError(f"{message} (user_id={user_id})")
        user = db.get(User, user_id)
        if not user:
            message = "ユーザーが見つかりません"
            logger.error(message, extra={"user_id": user_id})
            raise NonRetryableError(f"{message} (user_id={user_id})")
        # 連携データの取得（SELECT のみ）。enqueue 時に事前検証済みだが、実行時点で
        # 連携が失われた／旧形式のケースを二重ガードする。回復には再連携が要るため NonRetryable。
        try:
            source = build_draft_source(db, user)
        except ResumeDraftSourceUnavailableError as exc:
            logger.info("経歴書ドラフト生成の入力が未整備: %s", exc)
            raise NonRetryableError(get_error("agent.draft_link_required")) from exc

        cache.status = "processing"
        cache.started_at = _now()
        cache.error_message = None
        db.commit()

    # ── フェーズB: LLM 生成 + PDF レンダリング検証（DB セッション無し）──────
    try:
        result = await run_resume_draft(model, source)
    except LLMError as exc:
        _charge_consumed_usage(session_factory, user_id, exc.usage, usage_description)
        raise NonRetryableError(get_error("agent.llm_failed")) from exc
    except AgentResponseParseError as exc:
        _charge_consumed_usage(session_factory, user_id, exc.usage, usage_description)
        raise NonRetryableError(get_error("agent.parse_failed")) from exc

    # PDF レンダリングを検証する。失敗した場合は課金せず dead_letter にする
    # （稀な実装/環境エラーでユーザーに課金しない不変条件 / 同期版 router と同一）。
    try:
        build_resume_pdf(result.payload)
    except Exception as exc:
        logger.error("経歴書ドラフト PDF のレンダリングに失敗", exc_info=True)
        raise NonRetryableError(get_error("agent.draft_pdf_failed")) from exc

    # ── フェーズC: 課金確定 → 結果書き戻し（新セッション）──────────────────
    # 本課金は PDF レンダリング成功後にのみ行う。課金記録の失敗は NonRetryable に包んで
    # dead_letter にし、リトライによる LLM 再実行（＝再課金）を防ぐ。
    with session_factory() as db:
        try:
            credit_service.record_chat_usage(
                db, user_id, result.usage, description=usage_description
            )
        except Exception as exc:
            logger.error("経歴書ドラフト生成のクレジット消費記録に失敗", exc_info=True)
            raise NonRetryableError("課金記録に失敗しました") from exc

    with session_factory() as db:
        cache = ResumeDraftCacheRepository(db).get_by_user(user_id)
        if not cache:
            logger.warning("結果書き戻し時にキャッシュが見つかりません", extra={"user_id": user_id})
            return
        cache.result = result.payload
        cache.status = "completed"
        cache.error_message = None
        cache.completed_at = _now()
        db.commit()


def _charge_consumed_usage(
    session_factory: SessionFactory, user_id: str, usage, usage_description: str
) -> None:
    """LLM/パース失敗時に、消費済みトークン（API 原価が発生済み）を課金する。

    課金記録自体の失敗はログに残して握りつぶす（本来の LLM/パース失敗を dead_letter として
    確定させることを優先する。課金の取りこぼしより二重の状態破壊を避ける / ADR-0012）。
    """
    if usage is None:
        return
    with session_factory() as db:
        try:
            credit_service.record_chat_usage(db, user_id, usage, description=usage_description)
        except Exception:
            logger.error("失敗パスでのクレジット消費記録に失敗", exc_info=True)
