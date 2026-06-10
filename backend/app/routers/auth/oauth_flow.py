"""
OAuth state生成・検証・GitHub authorization URL構築・frontend URL解決を担うモジュール。
"""

import logging
import secrets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, Request, status

from ...core.errors import ErrorCode, raise_app_error
from ...core.messages import get_error
from ...core.settings import get_callback_base_url, get_cors_origins, get_github_client_id

logger = logging.getLogger(__name__)

# 他モジュールが oauth_flow 経由でインポートできるよう再エクスポート
__all__ = [
    "get_default_frontend_origin",
    "get_default_frontend_url",
    "get_frontend_origin",
    "normalize_frontend_url",
    "resolve_frontend_url_from_request",
    "resolve_frontend_url_from_cookie",
    "build_external_base_url",
    "build_frontend_redirect_url",
    "validate_github_oauth_state",
    "build_github_authorization_url",
    "begin_github_oauth",
]


def get_default_frontend_origin() -> str:
    """CORS_ORIGINS の先頭を返す。未設定の場合は503を発生させる。"""
    origins = get_cors_origins()
    if not origins:
        raise_app_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.INTERNAL_ERROR,
            message=get_error("auth.cors_origins_not_configured"),
            action="システム管理者に連絡してください",
        )
    return origins[0]


def get_default_frontend_url() -> str:
    """デフォルトのフロントエンド URL を返す。"""
    return f"{get_default_frontend_origin().rstrip('/')}/"


def get_frontend_origin(frontend_url: str) -> str:
    """許可済み frontend_url からオリジンだけを取り出す。"""
    normalized = normalize_frontend_url(frontend_url)
    parsed = urlsplit(normalized)
    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_frontend_url(frontend_url: str) -> str:
    """
    フロントエンド URL を正規化する。

    scheme が http/https 以外、または CORS_ORIGINS に含まれないオリジンの場合は400を発生させる。
    """
    parsed = urlsplit(frontend_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise_app_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("auth.invalid_return_to"),
            action="ログイン元の画面から再度やり直してください",
        )

    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in get_cors_origins():
        raise_app_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("auth.frontend_origin_not_allowed"),
            action="許可されたフロントエンドから再度アクセスしてください",
        )

    path = parsed.path or "/"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )


def resolve_frontend_url_from_request(
    request: Request,
    return_to: str | None = None,
) -> str:
    """
    リクエストからフロントエンド URL を解決する。

    優先順位: return_to クエリパラメータ → Referer ヘッダー → Origin ヘッダー → デフォルト
    """
    if return_to:
        return normalize_frontend_url(return_to)

    referer = request.headers.get("referer")
    if referer:
        try:
            return normalize_frontend_url(referer)
        except HTTPException:
            logger.debug("Referer が CORS_ORIGINS に含まれないためスキップ: %s", referer)

    request_origin = request.headers.get("origin")
    if request_origin:
        return normalize_frontend_url(request_origin)

    return get_default_frontend_url()


def resolve_frontend_url_from_cookie(stored_url: str | None) -> str:
    """Cookie に保存された URL を解決する。無効な場合はデフォルト URL を返す。"""
    if stored_url:
        try:
            return normalize_frontend_url(stored_url)
        except HTTPException:
            logger.warning("Cookie に保存されたリダイレクト URL が無効なためデフォルトを使用: %s", stored_url)
    return get_default_frontend_url()


def build_external_base_url(request: Request) -> str:
    """リクエストヘッダーからリバースプロキシ考慮済みの外部 URL を構築する。"""
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
    scheme = forwarded_proto if forwarded_proto in {"http", "https"} else request.url.scheme

    forwarded_host = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    host = forwarded_host or request.headers.get("host") or request.url.netloc

    return f"{scheme}://{host}"


def build_frontend_redirect_url(
    frontend_url: str,
    error: str | None = None,
) -> str:
    """
    フロントエンドへのリダイレクト URL を構築する。

    エラーがある場合は github_error クエリパラメータを付与する。
    """
    if not error:
        return frontend_url

    parsed = urlsplit(frontend_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "github_error"
    ]
    query.append(("github_error", error))
    path = parsed.path or "/"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, path, urlencode(query), parsed.fragment)
    )


def validate_github_oauth_state(
    stored_state: str | None,
    provided_state: str | None,
) -> None:
    """
    GitHub OAuth の state を検証する。

    state が一致しない場合は401を発生させる。
    """
    if not stored_state or not provided_state:
        raise_app_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.AUTH_EXPIRED,
            message=get_error("auth.oauth_state_invalid"),
            action="GitHub ログインをやり直してください",
        )
    if not secrets.compare_digest(stored_state, provided_state):
        raise_app_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.AUTH_EXPIRED,
            message=get_error("auth.oauth_state_invalid"),
            action="GitHub ログインをやり直してください",
        )


def build_github_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    """GitHub OAuth 認可 URL を構築する。"""
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user",
            "state": state,
        }
    )
    return f"https://github.com/login/oauth/authorize?{query}"


def begin_github_oauth(
    request: Request,
    frontend_url: str,
) -> tuple[str, str]:
    """
    GitHub OAuth フローを開始する。

    state を生成して返す。呼び出し側（router）が HttpOnly Cookie に保存し、
    コールバックでサーバー側照合する（CSRF 対策の正本）。フロントの sessionStorage
    照合は多層防御として併用する。
    コールバック URL は `/github/callback` (フロントの React ルート) に揃える。
    CALLBACK_BASE_URL が設定されている場合は redirect_uri を固定し、
    未設定の場合は frontend_url のオリジンからフォールバックする。

    GITHUB_CLIENT_ID が未設定の場合は503を発生させる。

    Args:
        frontend_url: 認証完了後の遷移先。CALLBACK_BASE_URL 未設定時に redirect_uri のベースとして使用する。

    Returns:
        (authorization_url, state) のタプル
    """
    client_id = get_github_client_id()
    if not client_id:
        raise_app_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.INTERNAL_ERROR,
            message=get_error("auth.github_oauth_not_configured"),
            action="システム管理者に連絡してください",
        )

    callback_base = get_callback_base_url() or get_frontend_origin(frontend_url)
    redirect_uri = f"{callback_base}/github/callback"
    state = secrets.token_urlsafe(32)

    authorization_url = build_github_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
    )
    return authorization_url, state
