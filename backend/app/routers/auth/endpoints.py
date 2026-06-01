"""
認証エンドポイント定義。

各関数は薄いラッパーとして実装し、ロジックはサブモジュールに委譲する。
"""

import json as _json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ...core.errors import ErrorCode, raise_app_error
from ...core.messages import get_error
from ...core.security.auth import (
    _decode_token,
    get_current_user,
    verify_refresh_token,
)
from ...core.security.dependencies import limiter
from ...core.settings import get_callback_base_url
from ...db import get_db
from ...repositories import UserRepository
from ...schemas import GitHubCallbackRequest, GitHubLoginUrlResponse, TokenResponse
from .github_auth import authenticate_github_user
from .oauth_flow import (
    begin_github_oauth,
    build_external_base_url,
    build_frontend_redirect_url,
    get_frontend_origin,
    resolve_frontend_url_from_cookie,
    resolve_frontend_url_from_request,
)
from .token_manager import (
    clear_auth_cookies,
    extract_refresh_token_from_session,
    set_auth_cookies,
)

# GitHub OAuth Callback URL のパス
# /github/callback はフロントの React ルートで受け取り、POST /auth/github/callback でトークン交換する。
# Cloudflare Pages の _redirects は /auth/* のみ Cloud Run に転送するため、
# GitHub がリダイレクトする /github/callback は SPA フォールバックで React が処理する。
GITHUB_CALLBACK_PATH = "/github/callback"

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _html_redirect(url: str) -> str:
    """200 + HTML リダイレクトを返す。

    一部の CDN / リバースプロキシは 303 レスポンスの Set-Cookie を除去することがあるため、
    200 の HTML で meta refresh + JS リダイレクトを使い Cookie の欠落を回避する。
    """
    js_url = _json.dumps(url)
    safe_url = url.replace('"', "&quot;")
    return (
        "<!DOCTYPE html><html><head>"
        f'<meta http-equiv="refresh" content="0;url={safe_url}">'
        "</head><body>"
        f"<script>window.location.replace({js_url});</script>"
        "</body></html>"
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("20/minute")
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """リフレッシュトークンで新しいアクセストークンを発行する。"""
    token = extract_refresh_token_from_session(request)
    if not token:
        raise_app_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.AUTH_REQUIRED,
            message=get_error("auth.login_required"),
            action="ログインし直してください",
        )
    username, jti = verify_refresh_token(token)

    user = UserRepository(db).get_by_username(username)
    if not user:
        raise_app_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.AUTH_REQUIRED,
            message=get_error("auth.user_not_found"),
            action="ログインし直してください",
        )

    # DB の refresh_jti と一致しない場合は失効済みとして拒否する
    if user.refresh_jti != jti:
        raise_app_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.AUTH_EXPIRED,
            message=get_error("auth.invalid_token"),
            action="ログインし直してください",
        )

    set_auth_cookies(response, user.username, db)
    return TokenResponse(
        username=user.username,
        is_github_user=user.github_id is not None,
    )


@router.post("/logout", status_code=204)
@limiter.limit("20/minute")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    """ログアウト処理。DB の refresh_jti を無効化し Cookie を削除する。
    トークン解析が失敗した場合でも必ず Cookie を削除して 204 を返す。
    """
    token = extract_refresh_token_from_session(request)
    if token:
        try:
            payload = _decode_token(token)
            username: str | None = payload.get("sub")
            if username:
                user = UserRepository(db).get_by_username(username)
                if user:
                    UserRepository(db).update_refresh_jti(user, None)
        except HTTPException:
            logger.debug("ログアウト時のトークン解析に失敗（Cookie 削除を継続）", exc_info=True)
    clear_auth_cookies(response)


@router.get("/me", response_model=TokenResponse)
@limiter.limit("60/minute")
def me(request: Request, current_user=Depends(get_current_user)) -> TokenResponse:
    """現在のログインユーザー情報を返す。"""
    return TokenResponse(
        username=current_user.username,
        is_github_user=current_user.github_id is not None,
    )


@router.get("/github/login-url", response_model=GitHubLoginUrlResponse)
@limiter.limit("10/minute")
def github_login_url(
    request: Request,
    return_to: str | None = None,
) -> GitHubLoginUrlResponse:
    """GitHub OAuth 認可 URL と state を返す。

    state はフロントが sessionStorage に保持し、コールバック時に CSRF 検証する。
    """
    frontend_url = resolve_frontend_url_from_request(request, return_to)
    authorization_url, state = begin_github_oauth(request, frontend_url)
    return GitHubLoginUrlResponse(authorization_url=authorization_url, state=state)


@router.get("/github/login")
@limiter.limit("10/minute")
def github_login(
    request: Request,
    return_to: str | None = None,
) -> RedirectResponse:
    """GitHub OAuth 認可 URL へリダイレクトする。"""
    frontend_url = resolve_frontend_url_from_request(request, return_to)
    authorization_url, _state = begin_github_oauth(request, frontend_url)
    return RedirectResponse(url=authorization_url, status_code=status.HTTP_303_SEE_OTHER)


def _build_callback_html_response(
    frontend_url: str,
    *,
    error_message: str | None = None,
) -> HTMLResponse:
    """コールバック処理用の HTMLResponse を構築する。

    error_message が指定された場合は ``github_error`` クエリ付きの URL に、
    指定が無い場合は元の URL にリダイレクトする。
    """
    redirect_url = build_frontend_redirect_url(frontend_url, error_message)
    return HTMLResponse(content=_html_redirect(redirect_url))


@router.get("/github/callback")
@limiter.limit("10/minute")
async def github_callback_redirect(
    request: Request,
    code: str | None = None,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """GitHub OAuth コールバックを処理し、フロントエンドへリダイレクトする。

    一部の CDN / リバースプロキシは 303 レスポンスの Set-Cookie を除去することがあるため、
    200 + HTML リダイレクトで Cookie を確実にセットする。
    """

    # 現行フローでは GitHub のリダイレクト先はフロントの /github/callback（React ルート）であり、
    # フロントが sessionStorage の state を検証してから POST /auth/github/callback でトークン交換する。
    # このエンドポイントは後方互換のために残しているが、state のサーバー側検証は行わない。
    frontend_url = resolve_frontend_url_from_cookie(None)

    try:
        if not code:
            raise_app_error(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code=ErrorCode.AUTH_EXPIRED,
                message=get_error("auth.github_code_missing"),
                action="GitHub ログインをやり直してください",
            )
        callback_base = get_callback_base_url() or build_external_base_url(request)
        redirect_uri = f"{callback_base}/auth/github/callback"
        token_response = await authenticate_github_user(db, code, redirect_uri)
    except HTTPException as error:
        # error.detail は AppErrorResponse の dict 形式なので message フィールドを取り出す
        detail = error.detail
        error_message = detail.get("message") if isinstance(detail, dict) else str(detail)
        return _build_callback_html_response(frontend_url, error_message=error_message)

    response = _build_callback_html_response(frontend_url)
    set_auth_cookies(response, token_response.username, db)
    return response


@router.post("/github/callback", response_model=TokenResponse)
@limiter.limit("5/minute")
async def github_callback(
    request: Request,
    response: Response,
    payload: GitHubCallbackRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """GitHub OAuth コードを受け取り、認証 Cookie を発行する。

    state はフロントの sessionStorage で検証済みのためサーバー側では再検証しない。
    redirect_uri は GitHub OAuth App の登録値 (`/github/callback`) と一致させる必要がある。
    """
    frontend_url = resolve_frontend_url_from_request(request)
    callback_base = get_callback_base_url() or get_frontend_origin(frontend_url)
    redirect_uri = f"{callback_base}{GITHUB_CALLBACK_PATH}"
    token_response = await authenticate_github_user(db, payload.code, redirect_uri)
    set_auth_cookies(response, token_response.username, db)
    return token_response
