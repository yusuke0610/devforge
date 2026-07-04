"""DevForge Agent（LLM チャット）エンドポイント（ADR-0010）。

外部 LLM API を呼ぶ高コスト endpoint のため rate limit を付与する。
career_summary / self_pr スコープでは GitHub/ブログ分析サマリーを参照情報として付与する（DB は読み取りのみ）。
Agent のレスポンス（operations）はフロントの state にのみ適用され、DB は更新しない。
"""

import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.errors import ErrorCode, raise_app_error
from ..core.messages import get_error
from ..core.security.auth import get_current_user, require_github_user
from ..core.security.dependencies import limiter
from ..db import get_db
from ..models import User
from ..schemas.agent import AgentChatRequest, AgentChatResponse, ResumeDraftRequest
from ..services.agent import chat_service
from ..services.agent.chat_service import (
    AgentResponseParseError,
    AgentTargetNotFoundError,
    AgentUsage,
)
from ..services.agent.context_builder import build_reference_context
from ..services.agent.llm.base import LLMError
from ..services.agent.resume_draft.context import (
    ResumeDraftNoRepositoriesError,
    ResumeDraftSourceUnavailableError,
    build_draft_source,
)
from ..services.agent.resume_draft.draft_service import run_resume_draft
from ..services.billing import credit_service
from ..services.billing.credit_service import InsufficientCreditsError
from ..services.pdf.generators.resume_generator import build_resume_pdf
from .download_utils import stream_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _record_usage_after_llm(
    db: Session, user_id: str, usage: AgentUsage, *, description: str | None = None
) -> None:
    """LLM 応答後のクレジット消費・使用ログ記録を、ストリームを開き直してから行う。

    LLM 呼び出しの await 中にリクエストの DB セッションがアイドルになり、libSQL
    （Hrana over HTTP）のストリームが idle timeout で失効する。失効したまま commit
    すると `STREAM_EXPIRED` で 400 → 500 になり、課金記録も落ちる。`db.close()` で
    失効ストリームを解放しておけば、record_chat_usage 内の次の SELECT/commit が
    新しいコネクション（=新規 Hrana ストリーム）を取得して正常に確定できる。
    """
    db.close()
    credit_service.record_chat_usage(db, user_id, usage, description=description)


@router.post("/chat", response_model=AgentChatResponse)
@limiter.limit("10/minute")
async def agent_chat(
    request: Request,
    body: AgentChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentChatResponse:
    """選択スコープの内容とプロンプトをもとに、職務経歴書への差分 operations を返す。

    career_summary / self_pr スコープでは GitHub・ブログ分析サマリーを参照情報として付与する。
    レスポンスはフロントの state にのみ適用され、DB は更新しない
    （クレジット消費・使用ログの記録は除く / ADR-0012）。
    ユーザーが確認して「適用」した時点で既存の保存 API が呼ばれる。
    """
    # 有料モデル（sonnet）は LLM を呼ぶ前に残高をチェックする。実コストは応答後に
    # 確定するため事後減算とし、チェック通過後の負残高は許容する（ADR-0012）
    try:
        credit_service.ensure_can_use_model(db, user.id, body.model)
    except InsufficientCreditsError:
        raise_app_error(
            status_code=402,
            code=ErrorCode.INSUFFICIENT_CREDITS,
            message=get_error("billing.insufficient_credits"),
        )
    try:
        reference = build_reference_context(db, user.id, body.scope)
        result = await chat_service.run_agent_chat(body, reference)
    except AgentTargetNotFoundError:
        raise_app_error(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.target_not_found"),
        )
    except LLMError as exc:
        # リトライ呼び出しが失敗した場合、1 回目分の消費済みトークンを課金してから
        # 502 を返す（課金漏れを防ぐ / ADR-0012）。課金記録自体の失敗はログに残し、
        # 本来の LLM 失敗（502）を優先して返す
        if exc.usage is not None:
            try:
                _record_usage_after_llm(db, user.id, exc.usage)
            except Exception:
                logger.error("LLM 失敗時のクレジット消費記録に失敗", exc_info=True)
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_LLM_ERROR,
            message=get_error("agent.llm_failed"),
        )
    except AgentResponseParseError as exc:
        # リトライ後も失敗。消費済みトークン（リトライ含む API 原価）があれば課金を
        # 確定してから 502 を返す（課金漏れを防ぐ / ADR-0012）。課金記録自体の失敗は
        # ログに残し、本来のパース失敗（502）を優先して返す
        if exc.usage is not None:
            try:
                _record_usage_after_llm(db, user.id, exc.usage)
            except Exception:
                logger.error("パース失敗時のクレジット消費記録に失敗", exc_info=True)
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_PARSE_ERROR,
            message=get_error("agent.parse_failed"),
        )
    # 実トークン量に基づくクレジット消費 + 使用ログ記録（haiku はログのみ）。
    # 記録失敗は応答を返さず 500 にする（課金漏れを黙って通さない / ADR-0012）
    _record_usage_after_llm(db, user.id, result.usage)
    return result.response


@router.post("/resume-draft/pdf")
@limiter.limit("5/minute")
async def generate_resume_draft_pdf(
    request: Request,
    body: ResumeDraftRequest,
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """GitHub 連携データから経歴書ドラフトを生成し、PDF で返す（ADR-0018）。

    構造（プロジェクト・技術スタック・期間）は連携データからルールベースで写し、
    自然文（職務要約・自己PR・プロジェクト説明）だけを LLM で生成する。
    ドラフトは DB に保存しない（生成物はレスポンスの PDF のみ。
    クレジット消費・使用ログの記録は除く / ADR-0012）。
    """
    usage_description = f"経歴書ドラフト生成（{body.model}）"
    # 有料モデルは LLM を呼ぶ前に残高をチェックする（チャットと同一契約 / ADR-0012）
    try:
        credit_service.ensure_can_use_model(db, user.id, body.model)
    except InsufficientCreditsError:
        raise_app_error(
            status_code=402,
            code=ErrorCode.INSUFFICIENT_CREDITS,
            message=get_error("billing.insufficient_credits"),
        )
    # 連携キャッシュ + スキル証跡の読み取り（SELECT のみ）。未連携・旧形式・0 件は 409。
    # 0 件（NoRepositories）は再連携で回復しないため別導線を案内する（サブクラスを先に catch）
    try:
        source = build_draft_source(db, user)
    except ResumeDraftNoRepositoriesError as exc:
        logger.info("経歴書ドラフト生成: 分析対象リポジトリなし: %s", exc)
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.draft_no_repositories"),
            action="公開リポジトリを追加してから GitHub 連携を再実行してください",
        )
    except ResumeDraftSourceUnavailableError as exc:
        logger.info("経歴書ドラフト生成の入力が未整備: %s", exc)
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.draft_link_required"),
            action="サイドバーの「GitHub連携」から連携を実行してください",
        )
    try:
        result = await run_resume_draft(body.model, source)
    except LLMError as exc:
        # 失敗パスでも消費済みトークンの課金を確定させる（チャットと同一 / ADR-0012）
        if exc.usage is not None:
            try:
                _record_usage_after_llm(db, user.id, exc.usage, description=usage_description)
            except Exception:
                logger.error("LLM 失敗時のクレジット消費記録に失敗", exc_info=True)
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_LLM_ERROR,
            message=get_error("agent.llm_failed"),
        )
    except AgentResponseParseError as exc:
        if exc.usage is not None:
            try:
                _record_usage_after_llm(db, user.id, exc.usage, description=usage_description)
            except Exception:
                logger.error("パース失敗時のクレジット消費記録に失敗", exc_info=True)
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_PARSE_ERROR,
            message=get_error("agent.parse_failed"),
        )
    # 先に PDF を生成し、成功した場合のみ課金を確定する。build_resume_pdf は DB 非依存の
    # 同期処理なので _record_usage_after_llm（db.close を伴う）より前に実行してよい。
    # PDF 生成失敗（稀な実装/環境エラー）でユーザーに課金しないため、この順序にする。
    # LLM 呼び出し自体の失敗（上の except）はコストが発生済みなので従来どおり課金する（ADR-0012）
    pdf_bytes = build_resume_pdf(result.payload)
    # 実トークン量に基づくクレジット消費 + 使用ログ記録（記録失敗は 500 / ADR-0012）
    _record_usage_after_llm(db, user.id, result.usage, description=usage_description)
    return stream_pdf(pdf_bytes, "career-resume-draft.pdf")
