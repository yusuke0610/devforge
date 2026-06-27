"""GitHubLinkCacheRepository の単体テスト。

特に get_or_create の競合パス（IntegrityError 後の再 SELECT 分岐）を検証する。
.claude/rules/backend/database.md「IntegrityError 後の再 SELECT は None を判定する」の
再発防止契約を守るためのテスト。DB はモックせず実 SQLite セッションを使う。
"""

import pytest
from app.models import GitHubLinkCache
from app.repositories import GitHubLinkCacheRepository, UserRepository
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _make_user(db: Session, username: str = "gh-user"):
    return UserRepository(db).create(username, email=f"{username}@test.com")


def test_get_by_user_returns_none_when_absent(db_session: Session):
    """キャッシュが無いユーザーでは None を返す。"""
    repo = GitHubLinkCacheRepository(db_session)
    assert repo.get_by_user("missing-user") is None


def test_get_or_create_creates_when_absent(db_session: Session):
    """キャッシュが無ければ新規作成して flush する（id が採番される）。"""
    user = _make_user(db_session)
    repo = GitHubLinkCacheRepository(db_session)

    cache = repo.get_or_create(user.id)

    assert cache.user_id == user.id
    assert cache.id is not None
    # 同一ユーザーで再度呼んでも新規作成せず同じ行を返す
    again = repo.get_or_create(user.id)
    assert again.id == cache.id


def test_get_or_create_returns_existing(db_session: Session):
    """既存キャッシュがあればそれを返し、重複作成しない。"""
    user = _make_user(db_session)
    existing = GitHubLinkCache(user_id=user.id, status="completed")
    db_session.add(existing)
    db_session.commit()

    repo = GitHubLinkCacheRepository(db_session)
    cache = repo.get_or_create(user.id)

    assert cache.id == existing.id
    assert cache.status == "completed"


def test_get_or_create_returns_existing_on_integrity_error(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """並列作成で user_id 一意制約に衝突しても、rollback 後の再 SELECT で既存行を返す。

    他リクエストが先に commit していたレースを再現する。最初の SELECT は行を見逃し
    （None）、INSERT で IntegrityError → rollback → 再 SELECT で既存行を取得する経路。
    """
    user = _make_user(db_session)
    # 先行リクエストが commit 済みの行（最初の get_by_user では見逃す想定）
    committed = GitHubLinkCache(user_id=user.id, status="processing")
    db_session.add(committed)
    db_session.commit()

    repo = GitHubLinkCacheRepository(db_session)
    real_get_by_user = repo.get_by_user
    calls = {"n": 0}

    def fake_get_by_user(uid: str):
        # 1 回目（INSERT 前のチェック）は None を返して create 分岐へ進ませる。
        # 2 回目以降（rollback 後の再 SELECT）は実クエリで既存行を返す。
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return real_get_by_user(uid)

    monkeypatch.setattr(repo, "get_by_user", fake_get_by_user)

    cache = repo.get_or_create(user.id)

    assert cache.id == committed.id
    assert calls["n"] == 2


def test_get_or_create_raises_runtime_error_when_reselect_none(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
):
    """IntegrityError 後の再 SELECT も None なら RuntimeError を上げる（None を握りつぶさない）。"""
    user = _make_user(db_session)
    repo = GitHubLinkCacheRepository(db_session)

    # get_by_user は常に None（行が見つからない異常状態）
    monkeypatch.setattr(repo, "get_by_user", lambda uid: None)

    # flush は一意制約衝突を模して IntegrityError を投げる
    def fake_flush():
        raise IntegrityError("INSERT", {}, Exception("UNIQUE constraint failed"))

    monkeypatch.setattr(db_session, "flush", fake_flush)

    with pytest.raises(RuntimeError, match="再取得に失敗"):
        repo.get_or_create(user.id)
