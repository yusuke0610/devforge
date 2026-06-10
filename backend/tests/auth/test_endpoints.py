"""routers/auth/endpoints に対応する統合テスト。

- /auth/refresh のアクセス/リフレッシュトークン分離
- /auth/logout の Cookie 削除と refresh_jti 失効
- /auth/me の現在ユーザー返却
- CSRF チェック
- 認証失敗ログ
- rate limit
"""

import json
import logging

from app.core.security.auth import (
    create_access_token,
    create_refresh_token,
)
from app.main import limiter

from conftest import auth_header

# ── /auth/refresh ────────────────────────────────────────────────


def test_access_token_cannot_be_used_as_refresh(client) -> None:
    """アクセストークンでリフレッシュエンドポイントを叩いて拒否されることを確認する。"""
    auth_header(client, "rftest")
    # session から access_token を取り出し、refresh_token として上書きする
    raw = client.cookies.get("session", "{}")
    data = json.loads(raw)
    data["refresh_token"] = data.get("access_token", "")
    client.cookies.set("session", json.dumps(data))

    response = client.post("/auth/refresh")

    assert response.status_code == 401


def test_refresh_token_cannot_access_api(client) -> None:
    """リフレッシュトークンで通常 API を叩いて拒否されることを確認する。"""
    auth_header(client, "apitest")
    # session の access_token をリフレッシュトークンで上書きする
    refresh_token, _ = create_refresh_token("apitest")
    raw = client.cookies.get("session", "{}")
    data = json.loads(raw)
    data["access_token"] = refresh_token
    client.cookies.set("session", json.dumps(data))

    response = client.get("/auth/me")

    assert response.status_code == 401


def test_refresh_issues_new_access_token(client) -> None:
    """有効なリフレッシュトークンで新しいアクセストークンが発行されることを確認する。"""
    auth_header(client, "refuser")

    response = client.post("/auth/refresh")

    assert response.status_code == 200
    assert response.json()["username"] == "refuser"
    assert "access_token=" in response.headers.get("set-cookie", "")


def test_refresh_rejects_revoked_jti(client) -> None:
    """DB の refresh_jti と一致しないトークンでリフレッシュが拒否されることを確認する。"""
    auth_header(client, "revokeduser")
    # jti が DB と一致しない別トークンを発行し、session の refresh_token を上書きする
    stale_token, _ = create_refresh_token("revokeduser")
    raw = client.cookies.get("session", "{}")
    data = json.loads(raw)
    data["refresh_token"] = stale_token
    client.cookies.set("session", json.dumps(data))

    response = client.post("/auth/refresh")

    assert response.status_code == 401


# ── /auth/logout ─────────────────────────────────────────────────


def test_logout_clears_cookies(client) -> None:
    """ログアウト後に認証 Cookie が削除されることを確認する。"""
    auth_header(client, "logoutuser")

    response = client.post("/auth/logout")

    assert response.status_code == 204
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token=" in set_cookie


def test_logout_invalidates_refresh_token(client) -> None:
    """ログアウト後にリフレッシュトークンで再認証できないことを確認する。"""
    auth_header(client, "logoutuser2")

    client.post("/auth/logout")
    response = client.post("/auth/refresh")

    assert response.status_code == 401


def test_logout_without_token_returns_204(client) -> None:
    """リフレッシュトークンなしでもログアウトが 204 を返すことを確認する。"""
    response = client.post("/auth/logout")

    assert response.status_code == 204


# ── /auth/me ─────────────────────────────────────────────────────


def test_me_returns_current_user(client) -> None:
    auth_header(client, "alice")

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "username": "alice",
        "is_github_user": False,
    }


# ── CSRF ─────────────────────────────────────────────────────────


def _csrf_resume_payload() -> dict:
    return {
        "full_name": "テスト",
        "email": "test@example.com",
        "career_summary": "要約",
        "self_pr": "自己PR",
        "experiences": [],
        "qualifications": [],
    }


def test_post_without_csrf_token_is_rejected(client) -> None:
    """CSRFトークンなしの POST リクエストが 403 で拒否されることを確認する。"""
    auth_header(client, "csrftest1")
    client.cookies.delete("csrf_token")

    response = client.post(
        "/api/resumes",
        json=_csrf_resume_payload(),
        # CSRF ヘッダーなし
    )

    assert response.status_code == 403


def test_post_with_invalid_csrf_token_is_rejected(client) -> None:
    """不正な CSRFトークンの POST リクエストが 403 で拒否されることを確認する。"""
    auth_header(client, "csrftest2")

    response = client.post(
        "/api/resumes",
        json=_csrf_resume_payload(),
        headers={"X-CSRF-Token": "invalid-token"},
    )

    assert response.status_code == 403


def test_post_with_valid_csrf_token_succeeds(client) -> None:
    """正しい CSRF トークンの POST リクエストが成功することを確認する。"""
    headers = auth_header(client, "csrftest3")

    response = client.post(
        "/api/resumes",
        json=_csrf_resume_payload(),
        headers=headers,
    )

    assert response.status_code == 201


def test_get_request_skips_csrf_check(client) -> None:
    """GET リクエストは CSRF チェックをスキップすることを確認する。"""
    auth_header(client, "csrftest4")

    response = client.get("/auth/me")

    assert response.status_code == 200


# ── 不正アクセス追跡: 認証失敗ログ ────────────────────────────────


def _auth_failed_records(records: list[logging.LogRecord]) -> list[logging.LogRecord]:
    """auth_failed イベント (devforge ロガー WARNING) のみ抽出する。

    `LogRecord.message` はフォーマット後にのみ設定される派生属性のため、
    常に値を返す `getMessage()` を使う方が堅牢（caplog 等のフォーマッタ設定差異に強い）。
    """
    return [r for r in records if r.name == "devforge" and r.getMessage() == "auth_failed"]


def test_auth_failed_logged_when_cookie_missing(client, caplog) -> None:
    """Cookie 無しで保護 API を叩くと reason=missing_cookie の WARNING が出ることを確認する。"""
    client.cookies.clear()
    with caplog.at_level(logging.WARNING, logger="devforge"):
        response = client.get("/auth/me")

    assert response.status_code == 401
    records = _auth_failed_records(caplog.records)
    assert any(getattr(r, "reason", None) == "missing_cookie" for r in records)


def test_auth_failed_logged_for_invalid_jwt(client, caplog) -> None:
    """不正な JWT で 401 + reason=jwt_decode_error がログされることを確認する。"""
    client.cookies.clear()
    client.cookies.set("session", json.dumps({"access_token": "not-a-valid-jwt"}))
    with caplog.at_level(logging.WARNING, logger="devforge"):
        response = client.get("/auth/me")

    assert response.status_code == 401
    records = _auth_failed_records(caplog.records)
    assert any(getattr(r, "reason", None) == "jwt_decode_error" for r in records)


def test_auth_failed_logged_for_user_not_found(client, caplog) -> None:
    """DB に存在しないユーザー名のトークンで reason=user_not_found がログされることを確認する。"""
    token = create_access_token("nonexistent-user-xyz")
    client.cookies.clear()
    client.cookies.set("session", json.dumps({"access_token": token}))
    with caplog.at_level(logging.WARNING, logger="devforge"):
        response = client.get("/auth/me")

    assert response.status_code == 401
    records = _auth_failed_records(caplog.records)
    assert any(getattr(r, "reason", None) == "user_not_found" for r in records)


# ── レートリミット ──────────────────────────────────────────────


def test_auth_me_rate_limited_after_threshold(client) -> None:
    """/auth/me が 60/分の上限を超えると 429 を返すことを確認する。"""
    auth_header(client, "rl-user")
    limiter.reset()
    statuses: list[int] = []
    for _i in range(65):
        resp = client.get("/auth/me")
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            break
    assert 429 in statuses
    # 上限到達前に少なくとも数件は 200 を返している
    assert statuses.count(200) >= 50
    limiter.reset()


