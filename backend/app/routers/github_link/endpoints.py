"""
GitHub 連携 API エンドポイント。

POST /api/github-link/run        — GitHub 連携パイプラインをバックグラウンド実行（202）
GET  /api/github-link/cache      — 保存済みの連携結果を取得
GET  /api/github-link/cache/status — 連携ステータスポーリング用
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from ...core.errors import ErrorCode, raise_app_error, resolve_async_error_code
from ...core.messages import get_error
from ...core.security.auth import get_current_user
from ...core.security.dependencies import limiter
from ...db import get_db
from ...models import User
from ...repositories.github_link import GitHubLinkCacheRepository
from ...repositories.skill import GitHubSkillRepository
from ...schemas.github_link import (
    CachedGitHubLinkResponse,
    GitHubLinkRequest,
    GitHubLinkResponse,
    ProgressResponse,
)
from ...schemas.github_skill import GitHubSkillsResponse
from ...schemas.shared import TaskAcceptedResponse, TaskStatusResponse
from ...services.intelligence.github_link_service import get_or_create_github_link_cache
from ...services.tasks import AsyncTaskCacheService, TaskType
from ._responses import to_skill_item

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github-link", tags=["github-link"])


def _raise_dispatch_failed() -> None:
    """タスクのディスパッチに失敗したときの 500 エラーを送出する。"""
    raise_app_error(
        status_code=500,
        code=ErrorCode.INTERNAL_ERROR,
        message=get_error("task.dispatch_failed"),
        action="しばらく待ってから再試行してください",
    )


def require_github_user(user: User = Depends(get_current_user)) -> User:
    """GitHub 連携には GitHub ログイン（``github_id`` 保持）が必須。未連携なら 403。

    ``start`` / ``retry`` の両エンドポイントで共通の認可ガード。
    """
    if user.github_id is None:
        raise_app_error(
            status_code=403,
            code=ErrorCode.AUTH_REQUIRED,
            message=get_error("github_link.github_login_required"),
            action="GitHub アカウントでログインし直してください",
        )
    return user


@router.get("/cache", response_model=CachedGitHubLinkResponse)
def get_cache(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存済みの連携結果を取得する。"""
    cache = GitHubLinkCacheRepository(db).get_by_user(user.id)
    if not cache:
        return CachedGitHubLinkResponse()
    # cache.result は GitHubLinkResponse(...).model_dump() を保存した JSON（dict | None）。
    # Pydantic v2 は dict を受け取ると検証済みモデルへコアース可能なので validate で型を絞る。
    result = (
        GitHubLinkResponse.model_validate(cache.result) if cache.result is not None else None
    )
    return CachedGitHubLinkResponse(
        result=result,
        status=cache.status,
        error_message=cache.error_message,
        error_code=resolve_async_error_code(cache.error_message),
        warning_message=cache.warning_message,
    )


@router.get("/progress", response_model=ProgressResponse)
async def get_link_progress(
    user: User = Depends(get_current_user),
):
    """GitHub 連携タスクの進捗を取得する（ポーリング用）。

    Redis にデータがない場合（タスク未開始・Redis 障害）は step_index=0 のデフォルトを返す。
    """
    from ...services.progress_service import get_progress

    data = await get_progress(user.id)
    return ProgressResponse(**data)


@router.get("/skills", response_model=GitHubSkillsResponse)
def get_skills(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GitHub 連携で推論した 3 層スキル（ADR-0016）を取得する。

    連携がまだ実行されていない場合は空配列を返す。
    """
    skills = GitHubSkillRepository(db, user.id).list_for_user()
    return GitHubSkillsResponse(skills=[to_skill_item(s) for s in skills])


@router.get("/cache/status", response_model=TaskStatusResponse)
def get_cache_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """連携ステータスを返す（軽量ポーリング用）。"""
    cache = GitHubLinkCacheRepository(db).get_by_user(user.id)
    if not cache:
        return TaskStatusResponse(status="completed")
    return TaskStatusResponse(
        status=cache.status,
        error_message=cache.error_message,
        error_code=resolve_async_error_code(cache.error_message),
    )


@router.post("/run", response_model=TaskAcceptedResponse, status_code=202)
@limiter.limit("5/minute")
async def start_github_link(
    request: Request,
    payload: GitHubLinkRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
):
    """GitHub 連携パイプラインをバックグラウンドで開始する。"""
    github_username = user.username

    # 進行中のタスクがあればそのステータスを返す
    cache = get_or_create_github_link_cache(db, user.id)
    service = AsyncTaskCacheService(db, cache)

    # DB 最新状態を取得しつつ pending へアトミック遷移。進行中なら早期リターン
    if not service.try_reset_to_pending():
        return TaskAcceptedResponse(status=cache.status)

    try:
        await service.dispatch(
            background_tasks,
            TaskType.GITHUB_LINK,
            {
                "user_id": user.id,
                "github_username": github_username,
                "github_token": user.github_token,
                "include_forks": payload.include_forks,
            },
            failure_message="タスクの開始に失敗しました",
            logger=logger,
        )
    except Exception:
        _raise_dispatch_failed()

    return TaskAcceptedResponse(status="pending")


@router.post("/run/retry", response_model=TaskAcceptedResponse, status_code=202)
@limiter.limit("5/minute")
async def retry_github_link(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: GitHubLinkRequest | None = None,
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
):
    """失敗した GitHub 連携タスクを手動で再実行する。

    ``dead_letter`` 状態のキャッシュのみ再実行可能。
    ``retry_count`` を 0 にリセットし、ステータスを ``pending`` に戻して再ディスパッチする。
    """
    cache = GitHubLinkCacheRepository(db).get_by_user(user.id)
    if not cache:
        raise_app_error(
            status_code=404,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("github_link.no_link_cache"),
            action="先に GitHub 連携を実行してください",
        )
    service = AsyncTaskCacheService(db, cache)
    if not service.is_retryable_terminal():
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("github_link.not_retryable", status=cache.status),
            action="タスクの完了または失敗を待ってから再試行してください",
        )

    github_username = user.username
    include_forks = payload.include_forks if payload else False

    # DB 最新状態を取得しつつアトミック遷移。並列リトライ競合を防ぐ
    if not service.try_reset_to_pending(reset_retry_count=True):
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("github_link.not_retryable", status=cache.status),
            action="タスクの完了または失敗を待ってから再試行してください",
        )

    try:
        await service.dispatch(
            background_tasks,
            TaskType.GITHUB_LINK,
            {
                "user_id": user.id,
                "github_username": github_username,
                "github_token": user.github_token,
                "include_forks": include_forks,
            },
            failure_message="タスクの再実行に失敗しました",
            logger=logger,
        )
    except Exception:
        _raise_dispatch_failed()

    return TaskAcceptedResponse(status="pending")
