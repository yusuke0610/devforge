"""
GitHub 連携 API エンドポイント。

POST /api/github-link/run        — GitHub 連携パイプラインをバックグラウンド実行（202）
GET  /api/github-link/cache      — 保存済みの連携結果を取得
GET  /api/github-link/cache/status — 連携ステータスポーリング用
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from ..core.errors import ErrorCode, raise_app_error, resolve_async_error_code
from ..core.messages import get_error
from ..core.security.auth import get_current_user
from ..core.security.dependencies import limiter
from ..db import get_db
from ..models import GitHubLinkCache, User
from ..schemas.github_link import (
    CachedGitHubLinkResponse,
    GitHubLinkRequest,
    ProgressResponse,
)
from ..schemas.shared import TaskStatusResponse
from ..services.tasks import AsyncTaskCacheService, TaskType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github-link", tags=["github-link"])


def _get_or_create_cache(db: Session, user_id: str) -> GitHubLinkCache:
    """ユーザーのキャッシュレコードを取得、なければ作成する。"""
    cache = db.query(GitHubLinkCache).filter_by(user_id=user_id).first()
    if not cache:
        cache = GitHubLinkCache(user_id=user_id)
        db.add(cache)
        db.flush()
    return cache


@router.get("/cache", response_model=CachedGitHubLinkResponse)
def get_cache(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存済みの連携結果を取得する。"""
    cache = db.query(GitHubLinkCache).filter_by(user_id=user.id).first()
    if not cache:
        return CachedGitHubLinkResponse()
    return CachedGitHubLinkResponse(
        result=cache.result,
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
    from ..services.progress_service import get_progress

    data = await get_progress(user.id)
    return ProgressResponse(**data)


@router.get("/cache/status", response_model=TaskStatusResponse)
def get_cache_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """連携ステータスを返す（軽量ポーリング用）。"""
    cache = db.query(GitHubLinkCache).filter_by(user_id=user.id).first()
    if not cache:
        return TaskStatusResponse(status="completed")
    return TaskStatusResponse(
        status=cache.status,
        error_message=cache.error_message,
        error_code=resolve_async_error_code(cache.error_message),
    )


@router.post("/run", status_code=202)
@limiter.limit("5/minute")
async def start_github_link(
    request: Request,
    payload: GitHubLinkRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GitHub 連携パイプラインをバックグラウンドで開始する。"""
    if not user.username.startswith("github:"):
        raise_app_error(
            status_code=403,
            code=ErrorCode.AUTH_REQUIRED,
            message=get_error("github_link.github_login_required"),
            action="GitHub アカウントでログインし直してください",
        )

    github_username = user.username.removeprefix("github:")

    # 進行中のタスクがあればそのステータスを返す
    cache = _get_or_create_cache(db, user.id)
    service = AsyncTaskCacheService(db, cache)

    # DB 最新状態を取得しつつ pending へアトミック遷移。進行中なら早期リターン
    if not service.try_reset_to_pending():
        return {"status": cache.status}

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
        raise_app_error(
            status_code=500,
            code=ErrorCode.INTERNAL_ERROR,
            message=get_error("task.dispatch_failed"),
            action="しばらく待ってから再試行してください",
        )

    return {"status": "pending"}


@router.post("/run/retry", status_code=202)
@limiter.limit("5/minute")
async def retry_github_link(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: GitHubLinkRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """失敗した GitHub 連携タスクを手動で再実行する。

    ``dead_letter`` 状態のキャッシュのみ再実行可能。
    ``retry_count`` を 0 にリセットし、ステータスを ``pending`` に戻して再ディスパッチする。
    """
    if not user.username.startswith("github:"):
        raise_app_error(
            status_code=403,
            code=ErrorCode.AUTH_REQUIRED,
            message=get_error("github_link.github_login_required"),
            action="GitHub アカウントでログインし直してください",
        )

    cache = db.query(GitHubLinkCache).filter_by(user_id=user.id).first()
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
            message=f"このタスクはリトライできない状態です（現在: {cache.status}）",
            action="タスクの完了または失敗を待ってから再試行してください",
        )

    github_username = user.username.removeprefix("github:")
    include_forks = payload.include_forks if payload else False

    # DB 最新状態を取得しつつアトミック遷移。並列リトライ競合を防ぐ
    if not service.try_reset_to_pending(reset_retry_count=True):
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=f"このタスクはリトライできない状態です（現在: {cache.status}）",
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
        raise_app_error(
            status_code=500,
            code=ErrorCode.INTERNAL_ERROR,
            message=get_error("task.dispatch_failed"),
            action="しばらく待ってから再試行してください",
        )

    return {"status": "pending"}
