"""ブログ連携アカウント CRUD と記事一覧 API の統合テスト。"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.repositories import BlogAccountRepository
from fastapi.testclient import TestClient
from sqlalchemy.orm.session import Session

from conftest import auth_header

# テスト中は外部 API 呼び出しをモックし、常にユーザーが存在する扱いにする
_VERIFY_PATCH = "app.services.blog.account_service.verify_user_exists"


def test_add_blog_account(client: TestClient) -> None:
    """POST でアカウント登録できること。"""
    headers = auth_header(client)
    with patch(_VERIFY_PATCH, new_callable=AsyncMock, return_value=True):
        resp = client.post(
            "/api/blog/accounts",
            json={
                "platform": "zenn",
                "username": "testuser",
            },
            headers=headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["platform"] == "zenn"
    assert data["username"] == "testuser"
    assert "id" in data


def test_add_blog_account_normalizes_article_url(client: TestClient) -> None:
    """記事 URL 入力でも username に正規化して登録できること。"""
    headers = auth_header(client)
    with patch(_VERIFY_PATCH, new_callable=AsyncMock, return_value=True) as mock_verify:
        resp = client.post(
            "/api/blog/accounts",
            json={
                "platform": "zenn",
                "username": "https://zenn.dev/testuser/articles/sample-post",
            },
            headers=headers,
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "testuser"
    mock_verify.assert_awaited_once_with("zenn", "testuser")


def test_add_account_user_not_found(client: TestClient) -> None:
    """存在しないユーザー名で登録すると 404。"""
    headers = auth_header(client)
    with patch(_VERIFY_PATCH, new_callable=AsyncMock, return_value=False):
        resp = client.post(
            "/api/blog/accounts",
            json={
                "platform": "zenn",
                "username": "nonexistent_user_xyz",
            },
            headers=headers,
        )
    assert resp.status_code == 404
    body = resp.json()
    assert body["message"] == "指定されたアカウントが見つかりません。ユーザー名を確認してください。"
    assert body["code"] == "VALIDATION_ERROR"


def test_add_account_invalid_url_returns_404(client: TestClient) -> None:
    """対応外ドメインの URL は 404 扱いで弾くこと。"""
    headers = auth_header(client)
    resp = client.post(
        "/api/blog/accounts",
        json={
            "platform": "zenn",
            "username": "https://example.com/testuser",
        },
        headers=headers,
    )

    assert resp.status_code == 404
    body = resp.json()
    assert body["message"] == "指定されたアカウントが見つかりません。ユーザー名を確認してください。"
    assert body["code"] == "VALIDATION_ERROR"


def test_add_duplicate_account(client: TestClient) -> None:
    """同じ platform は重複登録できないこと。"""
    headers = auth_header(client)
    with patch(_VERIFY_PATCH, new_callable=AsyncMock, return_value=True):
        client.post(
            "/api/blog/accounts",
            json={
                "platform": "zenn",
                "username": "testuser",
            },
            headers=headers,
        )
        resp = client.post(
            "/api/blog/accounts",
            json={
                "platform": "zenn",
                "username": "testuser2",
            },
            headers=headers,
        )
    assert resp.status_code == 409


def test_list_blog_accounts(client: TestClient) -> None:
    """GET でアカウント一覧取得。"""
    headers = auth_header(client)
    with patch(_VERIFY_PATCH, new_callable=AsyncMock, return_value=True):
        client.post(
            "/api/blog/accounts", json={"platform": "zenn", "username": "u1"}, headers=headers
        )
        client.post(
            "/api/blog/accounts", json={"platform": "note", "username": "u2"}, headers=headers
        )

    resp = client.get("/api/blog/accounts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_delete_blog_account(client: TestClient) -> None:
    """DELETE でアカウント解除 + 記事も削除。"""
    headers = auth_header(client)
    with patch(_VERIFY_PATCH, new_callable=AsyncMock, return_value=True):
        resp = client.post(
            "/api/blog/accounts",
            json={
                "platform": "zenn",
                "username": "testuser",
            },
            headers=headers,
        )
    account_id = resp.json()["id"]

    resp = client.delete(f"/api/blog/accounts/{account_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get("/api/blog/accounts")
    assert resp.json() == []


def test_update_blog_account_resets_articles_and_sync_state(
    client: TestClient, db_session: Session
) -> None:
    """PATCH で username を更新し、記事・同期状態を初期化する。"""
    headers = auth_header(client)
    with patch(_VERIFY_PATCH, new_callable=AsyncMock, return_value=True):
        resp = client.post(
            "/api/blog/accounts",
            json={
                "platform": "note",
                "username": "old-user",
            },
            headers=headers,
        )
    account_id = resp.json()["id"]

    from app.repositories import BlogArticleRepository, UserRepository

    user = UserRepository(db_session).get_by_username("testuser")
    assert user is not None
    account_repo = BlogAccountRepository(db_session, user.id)
    account = account_repo.get_by_id(account_id)
    assert account is not None
    account.last_synced_at = datetime.now(timezone.utc)
    db_session.commit()

    repo = BlogArticleRepository(db_session, user.id)
    repo.upsert_many(
        [
            {
                "account_id": account.id,
                "platform": "note",
                "external_id": "note-1",
                "title": "記事1",
                "url": "https://note.com/old-user/n/note-1",
                "published_at": "2026-04-01",
                "likes_count": 3,
                "summary": "要約",
                "tags": ["note"],
            },
        ]
    )

    with patch(
        "app.services.blog.account_service.verify_user_exists",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_verify:
        resp = client.patch(
            "/api/blog/accounts/note",
            json={"username": "new-user"},
            headers=headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "new-user"
    assert data["last_synced_at"] is None
    mock_verify.assert_awaited_once_with("note", "new-user")

    refreshed_account = account_repo.get_by_id(account_id)
    assert refreshed_account is not None
    assert refreshed_account.username == "new-user"
    assert refreshed_account.last_synced_at is None
    assert repo.count_by_user() == 0


def test_list_blog_articles(client: TestClient) -> None:
    """GET で記事一覧取得。"""
    auth_header(client)
    resp = client.get("/api/blog/articles")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_blog_articles_filter_platform(client: TestClient) -> None:
    """platform パラメータでフィルタ。"""
    auth_header(client)
    resp = client.get("/api/blog/articles?platform=zenn")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_blog_articles_returns_platform_and_tags(
    client: TestClient, db_session: Session
) -> None:
    headers = auth_header(client)

    with patch(_VERIFY_PATCH, new_callable=AsyncMock, return_value=True):
        resp = client.post(
            "/api/blog/accounts",
            json={
                "platform": "zenn",
                "username": "testuser",
            },
            headers=headers,
        )
    account_id = resp.json()["id"]

    from app.repositories import BlogArticleRepository, UserRepository

    user = UserRepository(db_session).get_by_username("testuser")
    assert user is not None
    repo = BlogArticleRepository(db_session, user.id)
    repo.upsert_many(
        [
            {
                "account_id": account_id,
                "platform": "zenn",
                "external_id": "slug-2",
                "title": "記事2",
                "url": "https://zenn.dev/testuser/articles/slug-2",
                "published_at": "2026-03-02",
                "likes_count": 5,
                "summary": "要約",
                "tags": ["Python", "FastAPI"],
            }
        ]
    )

    resp = client.get("/api/blog/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["platform"] == "zenn"
    assert data[0]["tags"] == ["Python", "FastAPI"]
