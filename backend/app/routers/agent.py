"""DevForge Agent（LLM チャット）エンドポイント（ADR-0010）。

外部 LLM API を呼ぶ高コスト endpoint のため rate limit を付与する。
career_summary / self_pr スコープでは GitHub 分析サマリーを参照情報として付与する（DB は読み取りのみ）。
Agent のレスポンス（operations）はフロントの state にのみ適用され、DB は更新しない。
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.errors import ErrorCode, raise_app_error, resolve_async_error_code
from ..core.messages import get_error
from ..core.security.auth import get_current_user, require_github_user
from ..core.security.dependencies import limiter
from ..db import get_db
from ..models import User
from ..repositories.resume_draft import ResumeDraftCacheRepository
from ..schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    ResumeDraftRequest,
    ResumeDraftResultResponse,
    ResumeImportResponse,
)
from ..schemas.shared import TaskAcceptedResponse, TaskStatusResponse
from ..services.agent import chat_service
from ..services.agent.chat_service import (
    AgentResponseParseError,
    AgentTargetNotFoundError,
)
from ..services.agent.context_builder import build_reference_context
from ..services.agent.llm.base import LLMError
from ..services.agent.resume_draft.context import (
    ResumeDraftNoRepositoriesError,
    ResumeDraftSourceUnavailableError,
    build_draft_source,
)
from ..services.agent.resume_draft.mapper import build_pdf_payload
from ..services.agent.resume_import.import_service import run_resume_import
from ..services.agent.resume_import.text_extract import (
    PdfExtractionError,
    ScannedPdfError,
    extract_pdf_text,
)
from ..services.pdf.generators.resume_generator import build_resume_pdf
from ..services.tasks import AsyncTaskCacheService, TaskType
from ._shared import enforce_agent_daily_limit
from .download_utils import stream_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
@limiter.limit("10/minute")
async def agent_chat(
    request: Request,
    body: AgentChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentChatResponse:
    """選択スコープの内容とプロンプトをもとに、職務経歴書への差分 operations を返す。

    career_summary / self_pr スコープでは GitHub 分析サマリーを参照情報として付与する。
    レスポンスはフロントの state にのみ適用され、DB は更新しない（ADR-0010）。
    ユーザーが確認して「適用」した時点で既存の保存 API が呼ばれる。
    abuse 防止は日次レート制限で行う（ADR-0023 で課金を撤去）。
    """
    # 日次利用上限（abuse 防止 / #521・ADR-0023）を LLM 呼び出し前に確認する
    enforce_agent_daily_limit(db, user.id)
    try:
        reference = build_reference_context(db, user.id, body.scope)
        result = await chat_service.run_agent_chat(body, reference)
    except AgentTargetNotFoundError:
        raise_app_error(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.target_not_found"),
        )
    except LLMError:
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_LLM_ERROR,
            message=get_error("agent.llm_failed"),
        )
    except AgentResponseParseError:
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_PARSE_ERROR,
            message=get_error("agent.parse_failed"),
        )
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
    abuse 防止は日次レート制限で行う（ADR-0023 で課金を撤去）。
    """
    # 日次利用上限（abuse 防止 / #521・ADR-0023）を生成開始前に確認する
    enforce_agent_daily_limit(db, user.id)
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
    # 保存 payload はプロジェクト明細のリスト（ADR-0026 決定 1）なので、
    # レンダリング時だけ Resume 互換の形へ包む
    pdf_bytes = build_resume_pdf(build_pdf_payload(cache.result))
    return stream_pdf(pdf_bytes, "career-resume-draft.pdf")


@router.get("/resume-draft/result", response_model=ResumeDraftResultResponse)
def get_resume_draft_result(
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
) -> ResumeDraftResultResponse:
    """完了済みの経歴書ドラフトの生成 payload を JSON で返す（ADR-0025 / #525）。

    生成タスクが保存した payload（Resume 互換）をそのまま返す。web はこれをフォーム state へ
    注入し、ユーザー確認後に既存の保存 API を呼ぶ（DB 非更新 / ADR-0010）。PDF プレビュー/DL の
    ``/resume-draft/pdf`` とは用途が異なるため別エンドポイントに分ける。未完了・結果なしは 409。
    """
    cache = ResumeDraftCacheRepository(db).get_by_user(user.id)
    if not cache or cache.status != "completed" or not cache.result:
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.draft_not_ready"),
            action="経歴書ドラフトの生成が完了してから再度お試しください",
        )
    return ResumeDraftResultResponse.model_validate(cache.result)


# 手持ち PDF 経歴書のアップロード上限（ADR-0024 / #527）。経歴書 PDF は通常数 MB 以内。
_MAX_PDF_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/resume-import/pdf", response_model=ResumeImportResponse)
@limiter.limit("5/minute")
async def import_resume_pdf(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResumeImportResponse:
    """手持ちの PDF 経歴書を構造化抽出し、フォーム注入用 payload を返す（ADR-0024）。

    テキスト埋め込み PDF のみ対応（スキャン PDF は 422 で案内）。抽出は Claude Haiku で
    行い、DB は更新しない（ADR-0010）。結果はフロントがフォーム state へ注入 → ユーザー
    確認 → 既存の保存 API を呼ぶ。abuse 防止は日次レート制限（#521 / ADR-0023）。
    """
    enforce_agent_daily_limit(db, user.id)

    data = await file.read()
    if len(data) > _MAX_PDF_UPLOAD_BYTES:
        raise_app_error(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.import_too_large"),
        )

    # テキスト抽出。非 PDF / 破損 / スキャン（テキスト非埋め込み）は明示的に 422 で倒す
    # （旧設計の空文字握りつぶしの再発防止 / ADR-0004→0008→0024）
    try:
        text = extract_pdf_text(data)
    except ScannedPdfError:
        raise_app_error(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.import_scanned_pdf"),
        )
    except PdfExtractionError:
        raise_app_error(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.import_invalid_pdf"),
        )

    # 構造化抽出（Claude Haiku 固定 / ADR-0023）。失敗契約はチャット・ドラフトと同一
    try:
        result = await run_resume_import("haiku", text)
    except LLMError:
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_LLM_ERROR,
            message=get_error("agent.llm_failed"),
        )
    except AgentResponseParseError:
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_PARSE_ERROR,
            message=get_error("agent.parse_failed"),
        )
    return ResumeImportResponse.model_validate(result.payload)
