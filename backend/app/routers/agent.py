"""DevForge Agent（LLM チャット）エンドポイント（ADR-0010）。

外部 LLM API を呼ぶ高コスト endpoint のため rate limit を付与する。
career_summary / self_pr スコープでは GitHub/ブログ分析サマリーを参照情報として付与する（DB は読み取りのみ）。
Agent のレスポンス（operations）はフロントの state にのみ適用され、DB は更新しない。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.errors import ErrorCode, raise_app_error, resolve_async_error_code
from ..core.messages import get_error
from ..core.security.auth import get_current_user, require_github_user
from ..core.security.dependencies import limiter
from ..db import get_db
from ..models import User
from ..repositories.resume_draft import ResumeDraftCacheRepository
from ..schemas.agent import AgentChatRequest, AgentChatResponse, ResumeDraftRequest
from ..schemas.shared import TaskAcceptedResponse, TaskStatusResponse
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
from ..services.billing import credit_service
from ..services.billing.credit_service import InsufficientCreditsError
from ..services.pdf.generators.resume_generator import build_resume_pdf
from ..services.tasks import AsyncTaskCacheService, TaskType
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


@router.post("/resume-draft/run", response_model=TaskAcceptedResponse, status_code=202)
@limiter.limit("5/minute")
async def start_resume_draft(
    request: Request,
    body: ResumeDraftRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
) -> TaskAcceptedResponse:
    """GitHub 連携データからの経歴書ドラフト生成をバックグラウンドで開始する（202 / ADR-0018）。

    構造（プロジェクト・技術スタック・期間）は連携データからルールベースで写し、自然文
    （職務要約・自己PR・プロジェクト説明）だけを LLM で生成する。生成物（payload）は
    ``resume_draft_cache`` に保存され、``GET /resume-draft/pdf`` でダウンロードできる。
    確定した職務経歴書（``resumes``）とは別物で、そちらには書き込まない。
    課金は生成タスク側で確定する（残高の事前チェックのみ本エンドポイントで行う / ADR-0012）。
    """
    # 有料モデルは生成を開始する前に残高をチェックする（チャットと同一契約 / ADR-0012）
    try:
        credit_service.ensure_can_use_model(db, user.id, body.model)
    except InsufficientCreditsError:
        raise_app_error(
            status_code=402,
            code=ErrorCode.INSUFFICIENT_CREDITS,
            message=get_error("billing.insufficient_credits"),
        )
    # 連携キャッシュ + スキル証跡の読み取り（SELECT のみ）で事前検証し、409 を即時に返す。
    # 0 件（NoRepositories）は再連携で回復しないため別導線を案内する（サブクラスを先に catch）
    try:
        build_draft_source(db, user)
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

    cache = ResumeDraftCacheRepository(db).get_or_create(user.id)
    service = AsyncTaskCacheService(db, cache)
    # DB 最新状態を取得しつつ pending へアトミック遷移。進行中なら現ステータスを返す。
    # dead_letter からの再実行も本メソッドが pending へ戻すため、生成ボタンが再試行を兼ねる。
    if not service.try_reset_to_pending(reset_retry_count=True):
        return TaskAcceptedResponse(status=cache.status)

    try:
        await service.dispatch(
            background_tasks,
            TaskType.RESUME_DRAFT,
            {"user_id": user.id, "model": body.model},
            failure_message="タスクの開始に失敗しました",
            logger=logger,
        )
    except Exception:
        raise_app_error(
            status_code=500,
            code=ErrorCode.INTERNAL_ERROR,
            message=get_error("task.dispatch_failed"),
            action="しばらく待ってから再試行してください",
        )

    return TaskAcceptedResponse(status="pending")


@router.get("/resume-draft/status", response_model=TaskStatusResponse)
def get_resume_draft_status(
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
) -> TaskStatusResponse:
    """経歴書ドラフト生成タスクのステータスを返す（軽量ポーリング用 / ADR-0018）。"""
    cache = ResumeDraftCacheRepository(db).get_by_user(user.id)
    if not cache:
        return TaskStatusResponse(status="completed")
    return TaskStatusResponse(
        status=cache.status,
        error_message=cache.error_message,
        error_code=resolve_async_error_code(cache.error_message),
    )


@router.get("/resume-draft/pdf")
def download_resume_draft_pdf(
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """完了済みの経歴書ドラフトを PDF で返す（ADR-0018）。

    生成タスクが保存した payload から PDF を再レンダリングする（決定論的・DB 非依存）。
    生成未完了・結果なしは 409 を返す。
    """
    cache = ResumeDraftCacheRepository(db).get_by_user(user.id)
    if not cache or cache.status != "completed" or not cache.result:
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.draft_not_ready"),
            action="経歴書ドラフトの生成が完了してから再度お試しください",
        )
    pdf_bytes = build_resume_pdf(cache.result)
    return stream_pdf(pdf_bytes, "career-resume-draft.pdf")
