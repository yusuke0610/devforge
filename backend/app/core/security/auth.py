import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import NoReturn

import jwt
from fastapi import Depends, Request, status
from sqlalchemy.orm import Session

from ...db import get_db
from ...models import User
from ..errors import ErrorCode, raise_app_error
from ..logging_utils import log_event
from ..messages import get_error
from ..settings import get_jwt_private_key, get_jwt_public_key

# アクセストークン Cookie 名（後方互換性のため公開）
_COOKIE_NAME = "access_token"
_REFRESH_COOKIE_NAME = "refresh_token"

# アクセストークン: 15分
_ACCESS_TOKEN_EXPIRE_MINUTES = 15
_COOKIE_MAX_AGE = _ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 900秒

# リフレッシュトークン: 7日
_REFRESH_TOKEN_EXPIRE_DAYS = 7
_REFRESH_COOKIE_MAX_AGE = _REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # 604800秒

_ALGORITHM = "RS256"


def validate_jwt_key_pair() -> None:
    """起動時に JWT 鍵ペアの整合性を検証する。署名 → 検証が通らない場合は RuntimeError を送出する。"""
    try:
        tok = jwt.encode(
            {"sub": "__bootstrap_check__"},
            get_jwt_private_key(),
            algorithm=_ALGORITHM,
        )
        jwt.decode(tok, get_jwt_public_key(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError as e:
        raise RuntimeError(
            f"JWT 鍵ペアが不正です（秘密鍵と公開鍵が一致しないか、フォーマットが壊れています）: {e}"
        ) from e


def create_access_token(username: str) -> str:
    """短命のアクセストークン（15分）を生成する。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": username, "type": "access", "exp": expire}
    return jwt.encode(payload, get_jwt_private_key(), algorithm=_ALGORITHM)


def create_refresh_token(username: str) -> tuple[str, str]:
    """長命のリフレッシュトークン（7日）を生成する。jti（UUID）を埋め込み (token, jti) を返す。"""
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": username, "type": "refresh", "exp": expire, "jti": jti}
    return jwt.encode(payload, get_jwt_private_key(), algorithm=_ALGORITHM), jti


def _raise_auth_failed(
    reason: str,
    *,
    code: ErrorCode = ErrorCode.AUTH_EXPIRED,
    message_key: str = "auth.invalid_token",
    with_bearer_header: bool = False,
) -> NoReturn:
    """認証失敗を構造化ログに残してから 401 を送出する。

    Cloud Logging で ``jsonPayload.message="auth_failed"`` でフィルタすれば、
    client_ip / path / method / reason 別に攻撃元・対象・原因を即座に集計できる。
    """
    log_event(logging.WARNING, "auth_failed", reason=reason, http_status=401, status="failed")
    raise_app_error(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=code,
        message=get_error(message_key),
        action="ログインし直してください",
        headers={"WWW-Authenticate": "Bearer"} if with_bearer_header else None,
    )


def _decode_token(token: str) -> dict:
    """JWT をデコードしてペイロードを返す。失敗時は 401 を送出する。"""
    try:
        return jwt.decode(token, get_jwt_public_key(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        _raise_auth_failed("jwt_decode_error", with_bearer_header=True)


def verify_refresh_token(token: str) -> tuple[str, str]:
    """リフレッシュトークンを検証し、(username, jti) を返す。DB 照合は行わない。"""
    payload = _decode_token(token)
    if payload.get("type") != "refresh":
        _raise_auth_failed("refresh_wrong_type")
    username: str | None = payload.get("sub")
    if not username:
        _raise_auth_failed("refresh_missing_sub")
    jti: str | None = payload.get("jti")
    if not jti:
        _raise_auth_failed("refresh_missing_jti")
    return username, jti


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    # session Cookie に JSON 形式で格納したアクセストークンを取り出す
    raw = request.cookies.get("session")
    if not raw:
        _raise_auth_failed(
            "missing_cookie",
            code=ErrorCode.AUTH_REQUIRED,
            message_key="auth.login_required",
        )
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        _raise_auth_failed("invalid_session_cookie")
    token = data.get("access_token") if isinstance(data, dict) else None
    if not token:
        _raise_auth_failed(
            "missing_access_token",
            code=ErrorCode.AUTH_REQUIRED,
            message_key="auth.login_required",
        )
    payload = _decode_token(token)
    if payload.get("type") != "access":
        _raise_auth_failed("access_wrong_type")
    username: str | None = payload.get("sub")
    if not username:
        _raise_auth_failed("access_missing_sub")

    from ...repositories import UserRepository

    user = UserRepository(db).get_by_username(username)
    if not user:
        _raise_auth_failed(
            "user_not_found",
            code=ErrorCode.AUTH_REQUIRED,
            message_key="auth.user_not_found",
        )
    return user


def require_github_user(user: User = Depends(get_current_user)) -> User:
    """GitHub 連携データを使う機能には GitHub ログイン（``github_id`` 保持）が必須。未連携なら 403。

    github-link の run / retry と経歴書ドラフト生成（ADR-0018）で共通の認可ガード。
    """
    if user.github_id is None:
        raise_app_error(
            status_code=403,
            code=ErrorCode.AUTH_REQUIRED,
            message=get_error("github_link.github_login_required"),
            action="GitHub アカウントでログインし直してください",
        )
    return user
