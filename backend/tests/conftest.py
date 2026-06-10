import json
import os
import secrets
from unittest.mock import AsyncMock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _generate_test_rsa_keys() -> tuple[str, str]:
    """テスト用 RSA 鍵ペアを生成して (秘密鍵PEM, 公開鍵PEM) を返す。"""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pem_public = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return pem_private, pem_public


# --- アプリケーション import より前に環境変数を確定する ---
# app.db.database が import 時に build_sqlalchemy_database_url() を評価するため、
# TURSO_DATABASE_URL を先に必ず設定しておく必要がある
_test_private_key, _test_public_key = _generate_test_rsa_keys()

os.environ.setdefault("JWT_PRIVATE_KEY", _test_private_key)
os.environ.setdefault("JWT_PUBLIC_KEY", _test_public_key)
# Turso (libSQL) 接続用のテスト DB。db_session fixture でテストごとに別 engine を生成して差し替える
os.environ.setdefault("TURSO_DATABASE_URL", "/tmp/devforge_test_default.db")
os.environ.setdefault("TURSO_AUTH_TOKEN", "")
os.environ.setdefault("APP_BOOTSTRAPPED", "1")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "pVo6M_raAWEpAv25F4p4RziywsjfPENokI10DZbNO7E=")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:8788")
os.environ.setdefault("TASK_RUNNER", "local")
os.environ.setdefault("UPSTASH_REDIS_URL", "redis://redis:6379")
os.environ.setdefault("UPSTASH_REDIS_TOKEN", "")
os.environ.setdefault("GCP_PROJECT_ID", "")
os.environ.setdefault("CLOUD_TASKS_QUEUE", "")
os.environ.setdefault("CLOUD_TASKS_LOCATION", "")
os.environ.setdefault("CLOUD_TASKS_SERVICE_URL", "")
os.environ.setdefault("CLOUD_TASKS_SERVICE_ACCOUNT", "")
os.environ.setdefault("COOKIE_SECURE", "true")
os.environ.setdefault("COOKIE_SAMESITE", "lax")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("INTERNAL_SECRET", "")
os.environ.setdefault("TASK_MAX_ATTEMPTS", "3")
os.environ.setdefault("CALLBACK_BASE_URL", "")
os.environ.setdefault("LOG_LEVEL", "")
os.environ.setdefault("LOG_FORMAT", "")
os.environ.setdefault("APP_VERSION", "")

import app.routers.internal as _internal_router  # noqa: E402
import app.services.tasks.local as _tasks_local  # noqa: E402
import app.services.tasks.worker as _worker  # noqa: E402
import pytest  # noqa: E402
from app.core.security.auth import create_access_token, create_refresh_token  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import app, limiter  # noqa: E402
from app.models import (  # noqa: F401,E402 — ensure models registered
    BlogAccount,
    BlogArticle,
    GitHubLinkCache,
    MQualification,
    MTechnologyStack,
    Resume,
    User,
)
from app.repositories import UserRepository  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402


@pytest.fixture()
def session_factory(tmp_path):
    """セッションファクトリ（呼ぶたびに新セッションを返す sessionmaker）。

    ハンドラの ``run(session_factory, payload)`` 引数に渡す前提。本番の
    ``SessionLocal`` と同様に「呼ぶたびに新セッション」を提供する。

    libSQL の Hrana 失効回避策で、ハンドラは外部 API 前後でセッションを開閉する設計に
    なっており、テストでも同じインターフェイスで呼べるよう本ファクトリを使う。
    ``expire_on_commit=False`` は本番 ``SessionLocal`` と揃える。
    """
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(
        autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
    )
    try:
        yield factory
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(session_factory):
    """テストごとに 1 つだけ払い出す互換セッション。

    セットアップ・検証用に使う。長時間処理を含むハンドラに渡すときは
    ``session_factory`` を直接使うこと（``run(session_factory, payload)``）。
    """
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db

    # execute_task をノーオペレーションに差し替える。
    # テスト用のインメモリDBとLLMを持たない環境でバックグラウンドタスクが
    # 実際に実行されると例外が発生し TestClient が伝播させてしまうため。
    # バックグラウンドタスクの動作を検証したいテストはワーカー関数を直接呼ぶこと。
    #
    # ``from ... import execute_task`` で各モジュールに束縛されたシンボルは
    # 元モジュール (_worker) への再代入では差し変わらないため、
    # 参照を保持している全モジュールを同じ AsyncMock に揃える。
    mock_execute_task = AsyncMock(return_value=None)
    originals = {
        module: module.execute_task for module in (_worker, _internal_router, _tasks_local)
    }
    for module in originals:
        module.execute_task = mock_execute_task

    limiter.reset()
    with TestClient(app) as c:
        c._db_session = db_session  # auth_header から参照するためセッションを保持
        yield c
    app.dependency_overrides.clear()
    for module, original in originals.items():
        module.execute_task = original


def make_resume_payload(**overrides) -> dict:
    """有効な職務経歴書 payload を生成する（トップレベルキーを overrides で上書き可）。

    取引先・プロジェクト・体制まで含む完全な構造を返す。呼ぶたびに新しい dict を返すので
    テスト間で共有しても副作用が無い。テスト固有の最小 payload や検証用の変種は
    各テスト側でそのまま定義してよい（intent を読みやすく残すため）。
    """
    payload: dict = {
        "full_name": "山田 太郎",
        "email": "yamada@example.com",
        "career_summary": "キャリアサマリー",
        "self_pr": "自己PR",
        "experiences": [
            {
                "company": "Example株式会社",
                "business_description": "SES事業",
                "start_date": "2021-04",
                "end_date": "2024-03",
                "is_current": False,
                "employee_count": "300",
                "capital": "10",
                "clients": [
                    {
                        "name": "顧客A",
                        "has_client": True,
                        "projects": [
                            {
                                "name": "プロジェクトA",
                                "start_date": "2021-04",
                                "end_date": "2022-03",
                                "is_current": False,
                                "role": "SE",
                                "description": "",
                                "team": {"total": "5", "members": []},
                                "technology_stacks": [],
                                "phases": [],
                            }
                        ],
                    }
                ],
            }
        ],
        "qualifications": [{"acquired_date": "2020-04", "name": "応用情報技術者"}],
    }
    payload.update(overrides)
    return payload


def auth_header(client, username: str = "testuser", *, github_id: int | None = None) -> dict:
    """テスト用の認証 Cookie をセットするヘルパー。CSRF トークンをヘッダーに含む dict を返す。

    DB にユーザーを直接作成し、JWT Cookie をセットする。
    /auth/register や /auth/login エンドポイントには依存しない。

    GitHub 連携を要するエンドポイント（github_id ベースのガード）をテストする場合は
    ``github_id`` を渡して GitHub ユーザーとして作成する。
    """
    db = client._db_session
    repo = UserRepository(db)
    if not repo.get_by_username(username):
        repo.create(username, email=f"{username}@example.com")

    access_token = create_access_token(username)
    refresh_token, jti = create_refresh_token(username)
    csrf_token = secrets.token_urlsafe(32)

    # refresh_jti を DB に保存（/auth/refresh の jti 照合テストで必要）
    user = repo.get_by_username(username)
    if user:
        user.refresh_jti = jti
        if github_id is not None:
            user.github_id = github_id
        db.commit()

    session_payload = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
    client.cookies.set("session", session_payload)
    client.cookies.set("csrf_token", csrf_token)

    return {"X-CSRF-Token": csrf_token}
