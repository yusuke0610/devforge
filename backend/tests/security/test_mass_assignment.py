"""mass-assignment 対策テスト。

作成・更新系の入力に `user_id` 等のサーバ管理フィールドを混ぜても、所有者が
攻撃者の指定どおりに移らない（サーバ側が認証ユーザーに固定する）ことを保証する。
"""

from app.repositories import ResumeRepository, UserRepository
from fastapi.testclient import TestClient

from conftest import auth_header, make_resume_payload


def test_resume_create_does_not_transfer_ownership(client: TestClient) -> None:
    """POST /api/resumes に他人の user_id を混ぜても、その他人は所有者にならない。"""
    db = client._db_session
    UserRepository(db).create("victim-a", email="victim-a@example.com")
    victim = UserRepository(db).get_by_username("victim-a")
    assert victim is not None

    headers = auth_header(client, "attacker-a")
    attacker = UserRepository(db).get_by_username("attacker-a")
    assert attacker is not None

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
    UserRepository(db).create("victim-b", email="victim-b@example.com")
    victim = UserRepository(db).get_by_username("victim-b")
    assert victim is not None

    headers = auth_header(client, "attacker-b")
    attacker = UserRepository(db).get_by_username("attacker-b")
    assert attacker is not None

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
