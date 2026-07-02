"""ブログ手動同期 API の統合テスト。"""

from unittest.mock import AsyncMock, patch

from app.models import BlogAccount
from app.repositories import BlogAccountRepository
from fastapi.testclient import TestClient
from sqlalchemy.orm.session import Session

from conftest import auth_header

_VERIFY_PATCH = "app.services.blog.account_service.verify_user_exists"


def test_sync_requires_auth(client: TestClient) -> None:
    """認証なしで sync → 401。"""
    resp = client.post("/api/blog/accounts/dummy-id/sync")
    assert resp.status_code == 401


def test_sync_account_returns_404_when_user_not_found(client: TestClient) -> None:
    """同期時の再検証で対象が見つからなければ 404 を返すこと。"""
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

    with patch(
        "app.services.blog.sync_service.verify_user_exists",
        new_callable=AsyncMock,
        return_value=False,
    ):
        resp = client.post(f"/api/blog/accounts/{account_id}/sync", headers=headers)

    assert resp.status_code == 404
    body = resp.json()
    assert body["message"] == "指定されたアカウントが見つかりません。ユーザー名を確認してください。"
    assert body["code"] == "VALIDATION_ERROR"


def test_sync_account_normalizes_saved_username_and_removes_stale_articles(
    client: TestClient, db_session: Session
) -> None:
    """保存済み URL を正規化し、同期結果に含まれない古い記事を削除すること。"""
    headers = auth_header(client)

    from app.repositories import BlogArticleRepository, UserRepository

    user = UserRepository(db_session).get_by_username("testuser")
    assert user is not None
    account = BlogAccount(
        user_id=user.id,
        platform="zenn",
        username="https://zenn.dev/testuser/articles/legacy-post",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)

    repo = BlogArticleRepository(db_session, user.id)
    repo.upsert_many(
        [
            {
                "account_id": account.id,
                "platform": "zenn",
                "external_id": "legacy-post",
                "title": "古い記事",
                "url": "https://zenn.dev/legacy/articles/legacy-post",
                "published_at": "2026-03-01",
                "likes_count": 10,
                "summary": "",
                "tags": ["Python"],
            },
        ]
    )

    with (
        patch(
            "app.services.blog.sync_service.verify_user_exists",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.blog.sync_service.fetch_articles",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_fetch_articles,
    ):
        resp = client.post(f"/api/blog/accounts/{account.id}/sync", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {"synced_count": 0, "total_count": 0}
    mock_fetch_articles.assert_awaited_once_with("zenn", "testuser")

    refreshed_account = BlogAccountRepository(db_session, user.id).get_by_id(account.id)
    assert refreshed_account is not None
    assert refreshed_account.username == "testuser"
    assert refreshed_account.last_synced_at is not None
    assert repo.count_by_user() == 0


def test_upsert_articles_no_duplicates(client: TestClient, db_session: Session) -> None:
    """同じ記事を2回 upsert しても重複しない。"""
    headers = auth_header(client)

    # アカウント作成
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

    # ユーザーIDを取得
    from app.repositories import BlogArticleRepository, UserRepository

    user = UserRepository(db_session).get_by_username("testuser")
    assert user is not None
    repo = BlogArticleRepository(db_session, user.id)

    articles = [
        {
            "account_id": account_id,
            "platform": "zenn",
            "external_id": "slug-1",
            "title": "記事1",
            "url": "https://zenn.dev/testuser/articles/slug-1",
            "published_at": "2026-03-01",
            "likes_count": 10,
            "summary": "",
            "tags": ["Python"],
        },
    ]

    count1 = repo.upsert_many(articles)
    assert count1 == 1

    # 同じ記事を再度 upsert
    count2 = repo.upsert_many(articles)
    assert count2 == 0

    # 合計1件のまま
    assert repo.count_by_user() == 1
