"""mass-assignment 対策テスト。

作成・更新系の入力に `user_id` 等のサーバ管理フィールドを混ぜても、所有者が
攻撃者の指定どおりに移らない（サーバ側が認証ユーザーに固定する）ことを保証する。
"""

from unittest.mock import AsyncMock, patch

from app.repositories import BlogAccountRepository, ResumeRepository, UserRepository
from fastapi.testclient import TestClient

from conftest import auth_header, make_resume_payload

_ACCOUNT_VERIFY_PATCH = "app.routers.blog.accounts.verify_user_exists"
_SERVICE_VERIFY_PATCH = "app.services.blog.account_service.verify_user_exists"


def test_resume_create_does_not_transfer_ownership(client: TestClient) -> None:
    """POST /api/resumes に他人の user_id を混ぜても、その他人は所有者にならない。"""
    db = client._db_session
    UserRepository(db).create("victim-a", hashed_password=None, email="victim-a@example.com")
    victim = UserRepository(db).get_by_username("victim-a")

    headers = auth_header(client, "attacker-a")
    attacker = UserRepository(db).get_by_username("attacker-a")

    payload = make_resume_payload(user_id=victim.id)
    resp = client.post("/api/resumes", json=payload, headers=headers)
    # extra フィールドは無視(201)または拒否(422)のいずれでも所有権移転は起きてはならない
    assert resp.status_code in (201, 422), f"unexpected {resp.status_code}: {resp.text}"

    # 被害者 B は決して所有者にならない
    assert ResumeRepository(db, victim.id).get_latest() is None
    if resp.status_code == 201:
        # 作成された場合は攻撃者自身に紐づく
        assert ResumeRepository(db, attacker.id).get_latest() is not None


def test_resume_update_does_not_transfer_ownership(client: TestClient) -> None:
    """PUT /api/resumes/{id} に他人の user_id を混ぜても所有者が移らない。"""
    db = client._db_session
    UserRepository(db).create("victim-b", hashed_password=None, email="victim-b@example.com")
    victim = UserRepository(db).get_by_username("victim-b")

    headers = auth_header(client, "attacker-b")
    attacker = UserRepository(db).get_by_username("attacker-b")

    created = client.post("/api/resumes", json=make_resume_payload(), headers=headers)
    assert created.status_code == 201
    resume = ResumeRepository(db, attacker.id).get_latest()
    assert resume is not None

    upd = client.put(
        f"/api/resumes/{resume.id}",
        json=make_resume_payload(user_id=victim.id, self_pr="更新後の自己PR"),
        headers=headers,
    )
    assert upd.status_code in (200, 422)

    # 所有権は攻撃者のまま。被害者には渡らない。
    assert ResumeRepository(db, victim.id).get_latest() is None
    assert ResumeRepository(db, attacker.id).get_latest() is not None


def test_blog_account_create_does_not_transfer_ownership(client: TestClient) -> None:
    """POST /api/blog/accounts に他人の user_id を混ぜても、その他人は所有者にならない。"""
    db = client._db_session
    UserRepository(db).create("victim-blog-a", hashed_password=None, email="victim-blog-a@example.com")
    victim = UserRepository(db).get_by_username("victim-blog-a")

    headers = auth_header(client, "attacker-blog-a")
    attacker = UserRepository(db).get_by_username("attacker-blog-a")

    with patch(_ACCOUNT_VERIFY_PATCH, new_callable=AsyncMock, return_value=True):
        resp = client.post(
            "/api/blog/accounts",
            json={"platform": "zenn", "username": "attacker", "user_id": victim.id},
            headers=headers,
        )
    assert resp.status_code in (201, 422), f"unexpected {resp.status_code}: {resp.text}"

    assert BlogAccountRepository(db, victim.id).list_by_user() == []
    if resp.status_code == 201:
        accounts = BlogAccountRepository(db, attacker.id).list_by_user()
        assert len(accounts) == 1
        assert accounts[0].username == "attacker"


def test_blog_account_update_does_not_transfer_ownership(client: TestClient) -> None:
    """PATCH /api/blog/accounts/{platform} に他人の user_id を混ぜても所有者が移らない。"""
    db = client._db_session
    UserRepository(db).create("victim-blog-b", hashed_password=None, email="victim-blog-b@example.com")
    victim = UserRepository(db).get_by_username("victim-blog-b")

    headers = auth_header(client, "attacker-blog-b")
    attacker = UserRepository(db).get_by_username("attacker-blog-b")

    with patch(_ACCOUNT_VERIFY_PATCH, new_callable=AsyncMock, return_value=True), patch(
        _SERVICE_VERIFY_PATCH,
        new_callable=AsyncMock,
        return_value=True,
    ):
        created = client.post(
            "/api/blog/accounts",
            json={"platform": "zenn", "username": "before"},
            headers=headers,
        )
        assert created.status_code == 201
        updated = client.patch(
            "/api/blog/accounts/zenn",
            json={"username": "after", "user_id": victim.id},
            headers=headers,
        )
    assert updated.status_code in (200, 422), f"unexpected {updated.status_code}: {updated.text}"

    assert BlogAccountRepository(db, victim.id).list_by_user() == []
    accounts = BlogAccountRepository(db, attacker.id).list_by_user()
    assert len(accounts) == 1
    if updated.status_code == 200:
        assert accounts[0].username == "after"
