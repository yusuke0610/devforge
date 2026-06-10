"""routers/auth/oauth_flow とそれを経由する GitHub OAuth フローの統合テスト。

ユニット部:
- state 検証
- frontend URL のスキーム / netloc / CORS_ORIGINS 検証
- Cookie からの URL 解決

統合部:
- /auth/github/login-url の authorization_url / state / redirect_uri
- /auth/github/login の 303 リダイレクト
- /auth/github/callback (GET / POST) のトークン交換と Cookie 発行
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from app.routers.auth.oauth_flow import (
    normalize_frontend_url,
    resolve_frontend_url_from_cookie,
    validate_github_oauth_state,
)
from app.routers.auth.token_manager import GITHUB_OAUTH_STATE_COOKIE
from fastapi import HTTPException


def _seed_oauth_state(client, state: str) -> None:
    """認可開始で発行される state Cookie を擬似的にセットする。

    TestClient は Secure Cookie を http で再送しないため、ラウンドトリップではなく
    手動セットで state Cookie を用意する（conftest の auth_header と同じ方式）。
    """
    client.cookies.set(GITHUB_OAUTH_STATE_COOKIE, state)


def _find_set_cookie(response, name: str) -> str:
    """レスポンスの Set-Cookie 群から指定 Cookie 名のヘッダ 1 行を返す（無ければ ""）。

    複数 Cookie がマージされた文字列ではなく個別エントリで検証したい時に使う
    （他 Cookie の属性を誤って拾わないため）。
    """
    prefix = f"{name}="
    for key, value in response.headers.multi_items():
        if key.lower() == "set-cookie" and value.startswith(prefix):
            return value
    return ""


# ── state 検証テスト ─────────────────────────────────────────────────────


def test_validate_state_success() -> None:
    """state が一致する場合は例外が発生しないこと。"""
    validate_github_oauth_state("abc123", "abc123")


def test_validate_state_mismatch_raises_401() -> None:
    """state が不一致の場合は HTTP 401 が発生すること。"""
    with pytest.raises(HTTPException) as exc_info:
        validate_github_oauth_state("abc123", "xyz789")
    assert exc_info.value.status_code == 401


def test_validate_state_missing_stored_raises_401() -> None:
    """stored_state が None の場合は HTTP 401 が発生すること。"""
    with pytest.raises(HTTPException) as exc_info:
        validate_github_oauth_state(None, "abc123")
    assert exc_info.value.status_code == 401


def test_validate_state_missing_provided_raises_401() -> None:
    """provided_state が None の場合は HTTP 401 が発生すること。"""
    with pytest.raises(HTTPException) as exc_info:
        validate_github_oauth_state("abc123", None)
    assert exc_info.value.status_code == 401


# ── malformed redirect_uri テスト ───────────────────────────────────────


def test_normalize_frontend_url_invalid_scheme_raises_400() -> None:
    """http/https 以外のスキームでは HTTP 400 が発生すること。"""
    with patch(
        "app.routers.auth.oauth_flow.get_cors_origins",
        return_value=["https://example.com"],
    ):
        with pytest.raises(HTTPException) as exc_info:
            normalize_frontend_url("ftp://example.com/path")
        assert exc_info.value.status_code == 400


def test_normalize_frontend_url_no_netloc_raises_400() -> None:
    """netloc が空の場合は HTTP 400 が発生すること。"""
    with patch(
        "app.routers.auth.oauth_flow.get_cors_origins",
        return_value=["https://example.com"],
    ):
        with pytest.raises(HTTPException) as exc_info:
            normalize_frontend_url("https://")
        assert exc_info.value.status_code == 400


# ── frontend URL 許可リスト外テスト ─────────────────────────────────────


def test_normalize_frontend_url_not_in_cors_origins_raises_400() -> None:
    """CORS_ORIGINS に含まれないオリジンでは HTTP 400 が発生すること。"""
    with patch(
        "app.routers.auth.oauth_flow.get_cors_origins",
        return_value=["https://allowed.example.com"],
    ):
        with pytest.raises(HTTPException) as exc_info:
            normalize_frontend_url("https://evil.example.com/page")
        assert exc_info.value.status_code == 400


def test_normalize_frontend_url_allowed_origin_succeeds() -> None:
    """CORS_ORIGINS に含まれるオリジンは正常に正規化されること。"""
    with patch(
        "app.routers.auth.oauth_flow.get_cors_origins",
        return_value=["https://allowed.example.com"],
    ):
        result = normalize_frontend_url("https://allowed.example.com/dashboard")
    assert result == "https://allowed.example.com/dashboard"


# ── cookie からの URL 解決テスト ────────────────────────────────────────


def test_resolve_frontend_url_from_cookie_valid() -> None:
    """有効な Cookie URL が正規化されて返ること。"""
    with patch(
        "app.routers.auth.oauth_flow.get_cors_origins",
        return_value=["https://example.com"],
    ):
        result = resolve_frontend_url_from_cookie("https://example.com/")
    assert result == "https://example.com/"


def test_resolve_frontend_url_from_cookie_none_returns_default() -> None:
    """Cookie が None の場合はデフォルト URL が返ること。"""
    with patch(
        "app.routers.auth.oauth_flow.get_cors_origins",
        return_value=["https://default.example.com"],
    ):
        result = resolve_frontend_url_from_cookie(None)
    assert result == "https://default.example.com/"


def test_resolve_frontend_url_from_cookie_invalid_returns_default() -> None:
    """Cookie に不正な URL がある場合はデフォルト URL が返ること。"""
    with patch(
        "app.routers.auth.oauth_flow.get_cors_origins",
        return_value=["https://default.example.com"],
    ):
        result = resolve_frontend_url_from_cookie("ftp://bad-url.com")
    assert result == "https://default.example.com/"


# ── GitHub OAuth エンドポイント統合テスト ────────────────────────────────


def test_github_login_url_returns_state(client) -> None:
    """login-url エンドポイントが authorization_url と state を JSON で返すことを確認する。"""
    response = client.get(
        "/auth/github/login-url",
        headers={"Origin": "http://localhost:8788"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "https://github.com/login/oauth/authorize" in data["authorization_url"]
    assert isinstance(data["state"], str)
    assert len(data["state"]) > 0
    # state はサーバー側の HttpOnly Cookie にも保存される（CSRF 照合の正本）。
    # Cookie 値が JSON で返した state と一致していることまで確認する。
    state_cookie = _find_set_cookie(response, GITHUB_OAUTH_STATE_COOKIE)
    assert state_cookie, "state Cookie が Set-Cookie に存在すること"
    assert "HttpOnly" in state_cookie
    cookie_value = state_cookie[len(f"{GITHUB_OAUTH_STATE_COOKIE}=") :].split(";", 1)[0].strip('"')
    assert cookie_value == data["state"]
    # /auth/** rewrite を回避するため redirect_uri は /github/callback でなければならない
    parsed = urlparse(data["authorization_url"])
    redirect_uri = parse_qs(parsed.query)["redirect_uri"][0]
    assert redirect_uri.endswith("/github/callback")
    assert "/auth/github/callback" not in redirect_uri


def test_github_login_url_uses_frontend_origin_when_callback_base_url_unset(client) -> None:
    response = client.get(
        "/auth/github/login-url",
        headers={
            "Origin": "http://localhost:8788",
            "Host": "devforge-dev-XXXXX-an.a.run.app",
            "X-Forwarded-Proto": "https",
        },
    )

    assert response.status_code == 200
    parsed = urlparse(response.json()["authorization_url"])
    redirect_uri = parse_qs(parsed.query)["redirect_uri"][0]
    assert redirect_uri == "http://localhost:8788/github/callback"


def test_github_login_url_uses_callback_base_url_when_set(client) -> None:
    """CALLBACK_BASE_URL が設定されている場合、x-forwarded-host より優先されることを確認する。

    settings.py のドキュメントに従い、scheme 付きの URL（``https://<host>``）を期待値とする。
    GitHub OAuth は scheme 付きの redirect_uri しか受け付けないため、現実的な値で検証する。
    """
    with patch.dict(
        os.environ,
        {"CALLBACK_BASE_URL": "https://devforge-dev-XXXXX-an.a.run.app"},
    ):
        response = client.get(
            "/auth/github/login-url",
            headers={
                "Origin": "http://localhost:8788",
                "Host": "devforge-dev-XXXXX-an.a.run.app",
                "X-Forwarded-Proto": "https",
            },
        )

    assert response.status_code == 200
    parsed = urlparse(response.json()["authorization_url"])
    redirect_uri = parse_qs(parsed.query)["redirect_uri"][0]
    assert redirect_uri == "https://devforge-dev-XXXXX-an.a.run.app/github/callback"


def test_github_login_redirect_to_github(client) -> None:
    """GET /auth/github/login が GitHub の認可 URL に 303 リダイレクトすることを確認する。"""
    response = client.get(
        "/auth/github/login",
        params={"return_to": "http://localhost:8788/index.html"},
        headers={
            "Host": "devforge-dev-XXXXX-an.a.run.app",
            "X-Forwarded-Proto": "https",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "https://github.com/login/oauth/authorize" in response.headers["location"]
    parsed = urlparse(response.headers["location"])
    redirect_uri = parse_qs(parsed.query)["redirect_uri"][0]
    assert redirect_uri == "http://localhost:8788/github/callback"


def test_github_callback_redirect_returns_error_when_code_missing(client) -> None:
    """GET /auth/github/callback は code が無い場合、トークン交換せずエラー付きでフロントへリダイレクトする。

    state はフロントの sessionStorage で検証する設計のため、サーバー側では検証しない。
    """
    with patch("httpx.AsyncClient") as mock_async_client:
        response = client.get(
            "/auth/github/callback",
            follow_redirects=False,
        )

    assert response.status_code == 200
    assert mock_async_client.call_count == 0
    # 200 + HTML リダイレクト: デフォルトフロント (CORS_ORIGINS[0]) に github_error 付きで戻る
    assert "localhost:8788" in response.text
    assert "github_error=" in response.text


def test_github_callback_redirect_sets_auth_cookie(client) -> None:
    """GET /auth/github/callback は state 照合に成功すると認証 Cookie を発行する。

    認可開始時に発行された state Cookie とコールバックの state query が一致する場合のみ
    トークン交換に進み、デフォルトフロント (CORS_ORIGINS[0]) へリダイレクトする。
    """
    token_response = MagicMock()
    token_response.json.return_value = {"access_token": "github-access-token"}
    user_response = MagicMock()
    user_response.json.return_value = {"id": 12345, "login": "octocat"}

    _seed_oauth_state(client, "valid-state")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post.return_value = token_response
        mock_http.get.return_value = user_response
        mock_cls.return_value = mock_http

        response = client.get(
            "/auth/github/callback?code=test-code&state=valid-state",
            follow_redirects=False,
        )

    assert response.status_code == 200
    # 200 + HTML リダイレクト: フロントエンド URL が HTML 本文に含まれていることを確認する
    assert "localhost:8788" in response.text
    assert "access_token=" in response.headers["set-cookie"]
    # 使い捨ての state Cookie が Max-Age=0 で破棄されること（リプレイ防止）
    state_cookie = _find_set_cookie(response, GITHUB_OAUTH_STATE_COOKIE)
    assert state_cookie, "state Cookie の削除 Set-Cookie が存在すること"
    assert "max-age=0" in state_cookie.lower()


def test_github_callback_redirect_rejects_mismatched_state(client) -> None:
    """GET /auth/github/callback は state 不一致だとトークン交換せずエラーへリダイレクトする。

    Cookie の state と query の state が食い違う場合、外部 API を一切叩かず CSRF を防ぐ。
    """
    _seed_oauth_state(client, "real-state")

    with patch("httpx.AsyncClient") as mock_async_client:
        response = client.get(
            "/auth/github/callback?code=test-code&state=attacker-state",
            follow_redirects=False,
        )

    # HTML リダイレクト（200）で github_error を返し、トークン交換には進まない
    assert response.status_code == 200
    assert mock_async_client.call_count == 0
    assert "github_error=" in response.text
    # 認証 Cookie は発行されない
    assert "access_token=" not in response.headers.get("set-cookie", "")
    # 失敗経路でも state Cookie は Max-Age=0 で破棄され、リプレイ窓を残さない
    state_cookie = _find_set_cookie(response, GITHUB_OAUTH_STATE_COOKIE)
    assert state_cookie, "state Cookie の削除 Set-Cookie が存在すること"
    assert "max-age=0" in state_cookie.lower()


def test_github_callback_post_rejects_missing_state_cookie(client) -> None:
    """POST /auth/github/callback は state Cookie が無いと 401 で拒否する。

    API を直叩きして Cookie を持たない攻撃者のリクエストはトークン交換に進めない。
    """
    client.cookies.clear()  # 認可開始を経ていない（state Cookie 無し）

    with patch("httpx.AsyncClient") as mock_async_client:
        response = client.post(
            "/auth/github/callback",
            json={"code": "test-code", "state": "any-state-from-frontend"},
            headers={
                "Host": "devforge-dev-XXXXX-an.a.run.app",
                "X-Forwarded-Proto": "https",
            },
        )

    assert response.status_code == 401
    # state 照合より先に外部 API を叩いていないこと
    assert mock_async_client.call_count == 0


def test_github_callback_post_rejects_mismatched_state(client) -> None:
    """POST /auth/github/callback は Cookie と body の state 不一致を 401 で拒否する。

    攻撃者が任意の code/state を投げても、サーバー保持の state と一致しなければ通らない。
    """
    _seed_oauth_state(client, "real-state")

    with patch("httpx.AsyncClient") as mock_async_client:
        response = client.post(
            "/auth/github/callback",
            json={"code": "test-code", "state": "attacker-state"},
            headers={
                "Host": "devforge-dev-XXXXX-an.a.run.app",
                "X-Forwarded-Proto": "https",
            },
        )

    assert response.status_code == 401
    assert mock_async_client.call_count == 0


def test_github_callback_post_succeeds_with_matching_state(client) -> None:
    """POST /auth/github/callback は Cookie と body の state 一致でトークン交換に進む。

    照合成功後は使い捨ての state Cookie を破棄する（リプレイ防止）。
    """
    token_response = MagicMock()
    token_response.json.return_value = {"access_token": "github-access-token"}
    user_response = MagicMock()
    user_response.json.return_value = {"id": 67890, "login": "octo-post"}

    _seed_oauth_state(client, "matching-state")

    with patch("httpx.AsyncClient") as mock_cls:
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_http.post.return_value = token_response
        mock_http.get.return_value = user_response
        mock_cls.return_value = mock_http

        response = client.post(
            "/auth/github/callback",
            json={"code": "test-code", "state": "matching-state"},
            headers={
                "Host": "devforge-dev-XXXXX-an.a.run.app",
                "X-Forwarded-Proto": "https",
            },
        )

    assert response.status_code == 200
    # username に "github:" プレフィックスを付けない（素の login 名で保存する）
    assert response.json()["username"] == "octo-post"
    assert response.json()["is_github_user"] is True
    assert "access_token=" in response.headers["set-cookie"]
    # 照合済みの state Cookie が Max-Age=0 で破棄されること（リプレイ防止）
    state_cookie = _find_set_cookie(response, GITHUB_OAUTH_STATE_COOKIE)
    assert state_cookie, "state Cookie の削除 Set-Cookie が存在すること"
    assert "max-age=0" in state_cookie.lower()
    # GitHub への redirect_uri も /github/callback でトークン交換していることを確認する
    posted_kwargs = mock_http.post.call_args.kwargs
    assert posted_kwargs["json"]["redirect_uri"].endswith("/github/callback")
    assert "/auth/github/callback" not in posted_kwargs["json"]["redirect_uri"]


def test_github_callback_post_uses_frontend_origin_when_callback_base_url_unset(client) -> None:
    """ローカル開発では frontend の Origin を redirect_uri の base に使うことを確認する。"""
    token_response = MagicMock()
    token_response.json.return_value = {"access_token": "github-access-token"}
    user_response = MagicMock()
    user_response.json.return_value = {"id": 24680, "login": "octo-local"}

    _seed_oauth_state(client, "state-from-frontend")

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
            headers={
                "Origin": "http://localhost:8788",
                "Host": "localhost:8000",
            },
        )

    assert response.status_code == 200
    posted_kwargs = mock_http.post.call_args.kwargs
    assert posted_kwargs["json"]["redirect_uri"] == "http://localhost:8788/github/callback"
