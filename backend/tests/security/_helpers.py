"""tests/security パッケージ内で共有する定数とヘルパ。"""

from __future__ import annotations

from app.models import User
from app.repositories import UserRepository
from fastapi.testclient import TestClient
from sqlalchemy import func, select

#: 攻撃者が試しがちな SQL インジェクションペイロード。
SQLI_PAYLOADS: tuple[str, ...] = (
    "' OR '1'='1",
    "'; DROP TABLE users;--",
    '" OR 1=1 --',
    "' UNION SELECT id FROM users --",
    "admin'/*",
)

#: 適当な UUID v4 形式の文字列。実在しない resume_id として使う。
DUMMY_UUID = "00000000-0000-0000-0000-000000000001"


RESUME_PAYLOAD: dict = {
    "full_name": "山田 太郎",
    "career_summary": "キャリアサマリー",
    "self_pr": "自己PR",
    "experiences": [],
    "qualifications": [],
}


def create_resume(client: TestClient, headers: dict[str, str]) -> str:
    """resume を作成し、id を返す。"""
    resp = client.post("/api/resumes", json=RESUME_PAYLOAD, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def count_rows(db, model) -> int:
    """テーブルの行数を取得する。"""
    return db.scalar(select(func.count()).select_from(model)) or 0


def ensure_user(db, username: str) -> User:
    """指定 username のユーザーを取得または作成する。auth_header に依存せず直挿しする用途。"""
    repo = UserRepository(db)
    user = repo.get_by_username(username)
    if not user:
        user = repo.create(username, email=f"{username}@example.com")
    return user
