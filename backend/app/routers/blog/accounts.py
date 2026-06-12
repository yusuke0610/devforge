"""ブログ連携アカウント CRUD と記事一覧。"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ...core.messages import get_error
from ...core.security.auth import get_current_user
from ...core.security.dependencies import limiter
from ...db import get_db
from ...models import User
from ...repositories import BlogAccountRepository, BlogArticleRepository
from ...schemas import (
    BlogAccountCreate,
    BlogAccountResponse,
    BlogAccountUpdate,
    BlogArticleResponse,
)
from ...services.blog.account_service import (
    BlogAccountAlreadyRegisteredError,
    BlogAccountService,
)
from ...services.blog.collector import (
    BlogAccountNotFoundError,
    BlogPlatformRequestError,
    UnsupportedBlogPlatformError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/accounts", response_model=list[BlogAccountResponse])
def list_accounts(
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """連携アカウント一覧を取得する。"""
    repo = BlogAccountRepository(db, user.id)
    return repo.list_by_user()


@router.post("/accounts", response_model=BlogAccountResponse, status_code=201)
@limiter.limit("10/minute")
async def add_account(
    request: Request,
    body: BlogAccountCreate,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """連携アカウントを登録する。
    同じプラットフォームは1つまで。ユーザー存在チェックあり。
    """
    service = BlogAccountService(db, user.id)
    try:
        return await service.add_account(body.platform, body.username)
    except BlogAccountAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=409,
            detail=get_error("blog.account_already_registered"),
        ) from exc
    except UnsupportedBlogPlatformError as exc:
        raise HTTPException(
            status_code=400,
            detail=get_error("blog.platform_not_supported"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=get_error("blog.account_not_found"),
        ) from exc
    except BlogPlatformRequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=get_error("blog.account_check_failed"),
        ) from exc
    except BlogAccountNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=get_error("blog.account_not_found"),
        ) from exc


@router.patch("/accounts/{platform}", response_model=BlogAccountResponse)
@limiter.limit("10/minute")
async def update_account(
    request: Request,
    platform: str,
    body: BlogAccountUpdate,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """連携アカウントの username を更新し、同期状態を未同期に戻す。"""
    service = BlogAccountService(db, user.id)
    if not service.get_by_platform(platform):
        raise HTTPException(status_code=404, detail=get_error("blog.account_link_not_found"))

    try:
        return await service.update_username(platform, body.username)
    except BlogAccountNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=get_error("blog.account_not_found"),
        ) from exc
    except UnsupportedBlogPlatformError as exc:
        raise HTTPException(
            status_code=400,
            detail=get_error("blog.platform_not_supported"),
        ) from exc
    except BlogPlatformRequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=get_error("blog.account_check_failed"),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=get_error("blog.account_not_found"),
        ) from exc


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(
    account_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """連携アカウントを解除する。紐づく記事も削除される。"""
    account_repo = BlogAccountRepository(db, user.id)
    if not account_repo.delete(account_id):
        raise HTTPException(status_code=404, detail=get_error("blog.account_link_not_found"))


@router.get("/articles", response_model=list[BlogArticleResponse])
def list_articles(
    platform: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """DB に保存済みの記事一覧を取得する。"""
    repo = BlogArticleRepository(db, user.id)
    return repo.list_by_user(platform=platform)
