"""経歴書ドラフト生成タスクの実行サービス（非同期 / ADR-0018）。

worker（``services/tasks``）から呼ばれ、LLM でドラフト payload を生成 → PDF レンダリング検証
→ ``ResumeDraftCache`` へ保存する。状態遷移・失敗通知は worker が担い、本モジュールは
成功時に ``status="completed"`` + ``result`` を書き戻し、失敗時は ``NonRetryableError`` を raise する。

DB 書き込み（結果保存・状態遷移）は本モジュールと repository に閉じ込める。
``draft_service`` / ``mapper`` / ``context`` の DB 非依存原則（context は SELECT のみ）は維持する。

冪等性の不変条件（ADR-0018・0020。課金は ADR-0023 で撤去済み）:
  - 完了済み（``status="completed"`` かつ ``result`` あり）タスクの再配信は再実行しない
    （Cloud Tasks の at-least-once 再配信で LLM を無駄に再実行しないため）。
  - PDF レンダリング失敗時は結果を保存せず ``NonRetryableError`` で dead_letter にする。

libSQL (Hrana over HTTP) の idle stream timeout を避けるため、LLM 呼び出しの前後で
セッションを開閉する（run_github_link と同方針）。
"""

from datetime import datetime, timezone

from ....core.logging_utils import get_logger
from ....core.messages import get_error
from ....models import User
from ....repositories.resume_draft import ResumeDraftCacheRepository
from ....services.pdf.generators.resume_generator import build_resume_pdf
from ...tasks.exceptions import NonRetryableError
from ...tasks.handlers.base import SessionFactory
from ..chat_service import AgentResponseParseError
from ..llm.base import LLMError
from .context import ResumeDraftSourceUnavailableError, build_draft_source
from .draft_service import run_resume_draft
from .mapper import build_pdf_payload

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def run_resume_draft_task(session_factory: SessionFactory, payload: dict) -> None:
    """経歴書ドラフトを生成し、結果をキャッシュに保存する。

    フェーズ構成:
      - A: payload 検証 + 入力取得（SELECT）+ processing マーク（短命セッション）
      - B: LLM 生成 + PDF レンダリング検証（DB セッション無し）
      - C: 結果書き戻し（新セッション）

    失敗はすべて ``NonRetryableError`` で worker に dead_letter を委ねる
    （LLM/PDF 失敗はリトライで回復しないため）。
    """
    user_id = payload.get("user_id")
    model = payload.get("model")
    if not user_id or not model:
        message = "経歴書ドラフトタスクのペイロードが不正です"
        logger.error(message, extra={"payload_keys": list(payload.keys())})
        raise NonRetryableError(f"{message} (payload_keys={list(payload.keys())})")

    # ── フェーズA: 入力取得 + processing マーク ──────────────────────────────
    with session_factory() as db:
        cache = ResumeDraftCacheRepository(db).get_by_user(user_id)
        if not cache:
            message = "経歴書ドラフトキャッシュが見つかりません"
            logger.error(message, extra={"user_id": user_id})
            raise NonRetryableError(f"{message} (user_id={user_id})")
        # 冪等ガード: 既に completed かつ result があるなら再実行しない。
        # フェーズC の結果保存を確定した後、worker が ack する前にプロセスが落ちると
        # Cloud Tasks が同一メッセージを再配信しうる。ここで短絡しないと LLM を無駄に
        # 再実行する（手動再実行は router が status を pending へ戻すため本ガードには掛からない）。
        if cache.status == "completed" and cache.result:
            logger.info("経歴書ドラフトは完了済みのため再実行をスキップ", extra={"user_id": user_id})
            return
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
        raise NonRetryableError(get_error("agent.llm_failed")) from exc
    except AgentResponseParseError as exc:
        raise NonRetryableError(get_error("agent.parse_failed")) from exc

    # PDF レンダリングを検証する。失敗した場合は課金せず dead_letter にする
    # （稀な実装/環境エラーでユーザーに課金しない不変条件 / 同期版 router と同一）。
    # 保存する result.payload はプロジェクト明細のリスト（ADR-0026 決定 1）なので、
    # レンダリング時だけ Resume 互換の形へ包む。
    try:
        build_resume_pdf(build_pdf_payload(result.payload))
    except Exception as exc:
        logger.error("経歴書ドラフト PDF のレンダリングに失敗", exc_info=True)
        raise NonRetryableError(get_error("agent.draft_pdf_failed")) from exc

    # ── フェーズC: 結果書き戻し（新セッション）──────
    with session_factory() as db:
        cache = ResumeDraftCacheRepository(db).get_by_user(user_id)
        if not cache:
            # 結果の保存先（ユーザーの ResumeDraftCache）が消えた（例: ユーザー削除の
            # CASCADE）。保存先が無いだけなので終了する。
            logger.warning("結果書き戻し時にキャッシュが見つかりません", extra={"user_id": user_id})
            return
        cache.result = result.payload
        cache.status = "completed"
        cache.error_message = None
        cache.completed_at = _now()
        db.commit()
