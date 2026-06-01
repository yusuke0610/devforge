"""
GitHub API 呼び出し（アクセストークン交換・ユーザー情報取得）および DB upsert を担うモジュール。
"""

import logging

import httpx
from fastapi import status
from sqlalchemy.orm import Session

from ...core.encryption import encrypt_field
from ...core.errors import ErrorCode, raise_app_error
from ...core.logging_utils import log_event
from ...core.messages import get_error
from ...core.settings import get_github_client_id, get_github_client_secret
from ...repositories import UserRepository
from ...schemas import TokenResponse


async def authenticate_github_user(
    db: Session,
    code: str,
    redirect_uri: str | None = None,
) -> TokenResponse:
    """
    GitHub OAuth コードを使ってユーザーを認証する。

    アクセストークン交換 → GitHub ユーザー情報取得 → DB upsert の順に処理する。
    認可リクエストで redirect_uri を指定した場合は同じ値を渡すこと。
    """
    client_id = get_github_client_id()
    client_secret = get_github_client_secret()
    if not client_id or not client_secret:
        raise_app_error(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code=ErrorCode.INTERNAL_ERROR,
            message=get_error("auth.github_oauth_not_configured"),
            action="システム管理者に連絡してください",
        )

    token_payload: dict = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
    }
    if redirect_uri:
        token_payload["redirect_uri"] = redirect_uri

    async with httpx.AsyncClient() as client:
        # アクセストークンの交換
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json=token_payload,
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            log_event(
                logging.WARNING,
                "github_oauth_failed",
                error=token_data.get("error_description", "unknown"),
                github_error=token_data.get("error", "unknown"),
                redirect_uri=redirect_uri,
            )
            raise_app_error(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code=ErrorCode.AUTH_REQUIRED,
                message=get_error("auth.github_oauth_failed"),
                action="GitHub ログインをやり直してください",
            )

        # GitHub ユーザー情報の取得
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        github_user = user_resp.json()

    github_id = github_user.get("id")
    github_login = github_user.get("login")
    if not github_id or not github_login:
        raise_app_error(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code=ErrorCode.AUTH_REQUIRED,
            message=get_error("auth.github_user_info_failed"),
            action="GitHub ログインをやり直してください",
        )

    # DB upsert
    repo = UserRepository(db)
    user = repo.get_by_github_id(github_id)
    if not user:
        user = repo.create_github_user(
            username=github_login,
            github_id=github_id,
        )
        log_event(logging.INFO, "github_user_created", username=user.username)

    user.github_token = encrypt_field(access_token)
    db.commit()

    return TokenResponse(username=user.username, is_github_user=True)
