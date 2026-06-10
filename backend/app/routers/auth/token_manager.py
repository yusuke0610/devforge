"""
Cookie設定・削除・JWT生成・トークン検証を担うモジュール。
"""

import json
import logging
import secrets

from fastapi import Request, Response
from sqlalchemy.orm import Session

from ...core.security.auth import (
    _REFRESH_COOKIE_MAX_AGE,
    create_access_token,
    create_refresh_token,
)
from ...core.security.csrf import CSRF_COOKIE_NAME, set_csrf_cookie
from ...core.settings import get_cookie_samesite, get_cookie_secure
from ...repositories import UserRepository

logger = logging.getLogger(__name__)

# 認証セッション Cookie 名（access/refresh token を JSON でまとめて保持する）
GITHUB_OAUTH_SESSION_COOKIE = "session"

# GitHub OAuth state Cookie 名。
# CSRF 対策として認可開始時にサーバーが発行し、コールバックでサーバー側照合する。
# フロントの sessionStorage 照合は多層防御として併用するが、正本はこの HttpOnly Cookie。
GITHUB_OAUTH_STATE_COOKIE = "oauth_state"

# state Cookie の有効期間（秒）。認可開始からコールバック完了までの猶予。
_OAUTH_STATE_COOKIE_MAX_AGE = 600


def extract_refresh_token_from_session(request: Request) -> str | None:
    """session Cookie に JSON で格納された refresh_token を取り出す。

    refresh と logout の両方で同形のパース処理が必要なため集約する。
    Cookie 不在・JSON 不正・型不一致の場合は `None` を返す。
    """
    raw = request.cookies.get(GITHUB_OAUTH_SESSION_COOKIE)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        logger.debug("session Cookie の JSON パースに失敗", exc_info=True)
        return None
    if not isinstance(data, dict):
        return None
    token = data.get("refresh_token")
    return token if isinstance(token, str) else None


def set_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    """指定したキーと値で HttpOnly Cookie を設定する。"""
    response.set_cookie(
        key=key,
        value=value,
        httponly=True,
        secure=get_cookie_secure(),
        samesite=get_cookie_samesite(),
        max_age=max_age,
        path="/",
    )


def delete_cookie(response: Response, key: str, path: str = "/") -> None:
    """指定したキーの Cookie を削除する。"""
    response.delete_cookie(key=key, path=path)



def set_oauth_state_cookie(response: Response, state: str) -> None:
    """GitHub OAuth の state を HttpOnly Cookie に保存する。

    コールバック時に Cookie 値と provided state をサーバー側で照合し、CSRF を防ぐ。
    """
    set_cookie(response, GITHUB_OAUTH_STATE_COOKIE, state, _OAUTH_STATE_COOKIE_MAX_AGE)


def read_oauth_state_cookie(request: Request) -> str | None:
    """リクエストの Cookie から GitHub OAuth state を取り出す。未設定なら ``None``。"""
    return request.cookies.get(GITHUB_OAUTH_STATE_COOKIE)


def delete_oauth_state_cookie(response: Response) -> None:
    """GitHub OAuth state Cookie を削除する（照合後の使い捨て・リプレイ防止）。"""
    delete_cookie(response, GITHUB_OAUTH_STATE_COOKIE, path="/")


def set_auth_cookies(response: Response, username: str, db: Session) -> None:
    """アクセストークン・リフレッシュトークン・CSRF トークンを Cookie にセットし、refresh_jti を DB に保存する。"""
    access_token = create_access_token(username)
    refresh_token, jti = create_refresh_token(username)
    csrf_token = secrets.token_urlsafe(32)

    # 旧 Cookie の残留削除（移行期の互換）
    delete_cookie(response, "access_token")
    delete_cookie(response, "refresh_token")

    # アクセストークン・リフレッシュトークンを JSON で1つの session Cookie にまとめる（7日）
    session_payload = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
    set_cookie(response, GITHUB_OAUTH_SESSION_COOKIE, session_payload, _REFRESH_COOKIE_MAX_AGE)

    # CSRF トークン（httpOnly=False: JS から読み取れる）
    set_csrf_cookie(response, csrf_token)

    # refresh_jti を DB に保存
    user = UserRepository(db).get_by_username(username)
    if user:
        UserRepository(db).update_refresh_jti(user, jti)


def clear_auth_cookies(response: Response) -> None:
    """認証関連の Cookie をすべて削除する。"""
    delete_cookie(response, GITHUB_OAUTH_SESSION_COOKIE, path="/")
    # 旧 Cookie の削除（移行期の互換）
    delete_cookie(response, "access_token", path="/")
    delete_cookie(response, "refresh_token", path="/auth/")
    delete_cookie(response, "refresh_token", path="/auth/refresh")
    delete_cookie(response, CSRF_COOKIE_NAME, path="/")
