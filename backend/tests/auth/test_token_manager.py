"""token_manager に対応する単体テスト。

- RS256 アクセストークン / リフレッシュトークンの生成と検証
- Cookie の Secure / SameSite デフォルト値（settings 側のヘルパ経由）
- ログアウト時の Cookie 削除属性（max-age=0）
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.security.auth import (
    create_access_token,
    create_refresh_token,
)
from app.core.settings import get_cookie_samesite, get_cookie_secure
from app.routers.auth.token_manager import GITHUB_OAUTH_STATE_COOKIE
from jose import jwt

from conftest import _test_public_key, auth_header

# ── RS256 トークン生成・検証 ──────────────────────────────────────


def test_create_access_token_contains_username() -> None:
    token = create_access_token("alice")
    payload = jwt.decode(token, _test_public_key, algorithms=["RS256"])

    assert payload["sub"] == "alice"


def test_create_access_token_has_expiry() -> None:
    token = create_access_token("alice")
    payload = jwt.decode(token, _test_public_key, algorithms=["RS256"])

    assert "exp" in payload


def test_create_access_token_type_is_access() -> None:
    token = create_access_token("alice")
    payload = jwt.decode(token, _test_public_key, algorithms=["RS256"])

    assert payload["type"] == "access"


def test_create_refresh_token_type_is_refresh() -> None:
    token, jti = create_refresh_token("alice")
    payload = jwt.decode(token, _test_public_key, algorithms=["RS256"])

    assert payload["type"] == "refresh"
    assert payload["sub"] == "alice"
    assert payload["jti"] == jti


def test_hs256_token_rejected_by_rs256_verification() -> None:
    """HS256 で署名したトークンが RS256 の検証で拒否されることを確認する。"""
    hs256_token = jwt.encode({"sub": "alice", "type": "access"}, "secret", algorithm="HS256")

    with pytest.raises(Exception):
        jwt.decode(hs256_token, _test_public_key, algorithms=["RS256"])


# ── Cookie 設定（secure / samesite デフォルト） ───────────────────


def test_cookie_secure_defaults_false_for_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8788")

    assert get_cookie_secure() is False


def test_cookie_secure_defaults_true_when_non_local_origin_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://localhost:8788,https://app.example.com",
    )

    assert get_cookie_secure() is True


def test_cookie_samesite_defaults_lax_for_localhost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8788")

    assert get_cookie_samesite() == "lax"


def test_cookie_samesite_defaults_none_for_non_local_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COOKIE_SAMESITE", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "https://storage.googleapis.com")

    assert get_cookie_samesite() == "none"


# ── Cookie 属性検証（session Cookie の名称・HttpOnly・SameSite）──────────────


def test_github_callback_post_sets_session_cookie_with_httponly(client) -> None:
    """POST /auth/github/callback が HttpOnly の session Cookie を設定することを確認する。"""
    token_response = MagicMock()
    token_response.json.return_value = {"access_token": "github-access-token"}
    user_response = MagicMock()
    user_response.json.return_value = {"id": 11111, "login": "cookie-test-user"}

    # CSRF 対策の state Cookie をセット（body の state と一致させる）
    client.cookies.set(GITHUB_OAUTH_STATE_COOKIE, "state-from-frontend")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post.return_value = token_response
        mock_http.get.return_value = user_response
        mock_cls.return_value = mock_http

        response = client.post(
            "/auth/github/callback",
            json={"code": "test-code", "state": "state-from-frontend"},
            headers={"Origin": "http://localhost:8788"},
        )

    assert response.status_code == 200
    # HttpOnly / SameSite は session Cookie 自身のエントリで検証する。
    # マージ文字列だと oauth_state など他 Cookie の属性を誤って拾うため個別に判定する。
    session_cookie = next(
        (
            value
            for key, value in response.headers.multi_items()
            if key.lower() == "set-cookie" and value.startswith("session=")
        ),
        "",
    )
    assert session_cookie, "session Cookie が Set-Cookie に存在すること"
    # HttpOnly 属性が付与されていること
    assert "HttpOnly" in session_cookie
    # SameSite 属性が付与されていること（ローカルでは lax）
    assert "samesite=lax" in session_cookie.lower()
    # Firebase 時代の __session Cookie 名が使われていないこと
    assert "__session=" not in response.headers.get("set-cookie", "")


def test_logout_clears_session_cookie_with_max_age_zero(client) -> None:
    """POST /auth/logout が session Cookie を Max-Age=0 で削除することを確認する。"""
    auth_header(client, "logout-cookie-attr-user")

    response = client.post("/auth/logout")

    assert response.status_code == 204
    all_set_cookie = response.headers.get("set-cookie", "")
    # session Cookie が削除されていること（max-age=0 で上書き）
    assert "session=" in all_set_cookie
    assert "max-age=0" in all_set_cookie.lower()
    # Firebase 時代の __session Cookie 名が使われていないこと
    assert "__session=" not in all_set_cookie
