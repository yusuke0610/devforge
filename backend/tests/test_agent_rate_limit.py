"""Agent 日次レート制限の単体テスト（#521 / ADR-0023）。

決定論ロジック（上限判定・日次リセット）を実 SQLite で検証する（DB モックなし）。
"""

from datetime import date, datetime, timezone

import pytest
from app.core.date_utils import JST
from app.models import AgentDailyUsage, User
from app.repositories import UserRepository
from app.services.agent.rate_limit import (
    AgentRateLimitExceededError,
    enforce_daily_limit,
)
from sqlalchemy import select


def _make_user(db_session, username: str) -> User:
    repo = UserRepository(db_session)
    if not repo.get_by_username(username):
        repo.create(username, email=f"{username}@example.com")
        db_session.commit()
    user = repo.get_by_username(username)
    assert user is not None
    return user


def _count_row(db_session, user_id: str, usage_date: date) -> int | None:
    return db_session.execute(
        select(AgentDailyUsage.request_count).where(
            AgentDailyUsage.user_id == user_id,
            AgentDailyUsage.usage_date == usage_date,
        )
    ).scalar_one_or_none()


def test_under_limit_is_allowed_and_increments(db_session) -> None:
    """上限未満のリクエストは許可され、カウントが 1 増える。"""
    user = _make_user(db_session, "rl-under")

    count = enforce_daily_limit(db_session, user.id, limit=50)

    assert count == 1
    # DB にカウンタ行が作られ 1 になっている
    today = datetime.now(timezone.utc).astimezone(JST).date()
    assert _count_row(db_session, user.id, today) == 1


def test_up_to_limit_is_allowed_boundary(db_session) -> None:
    """境界: 上限 N 回目までは許可される（off-by-one 検証）。"""
    user = _make_user(db_session, "rl-boundary")

    counts = [enforce_daily_limit(db_session, user.id, limit=3) for _ in range(3)]

    assert counts == [1, 2, 3]  # 3 回目（= limit）までは raise しない


def test_over_limit_raises(db_session) -> None:
    """上限超過（N+1 回目）で AgentRateLimitExceededError を raise する。"""
    user = _make_user(db_session, "rl-over")
    for _ in range(2):
        enforce_daily_limit(db_session, user.id, limit=2)

    with pytest.raises(AgentRateLimitExceededError):
        enforce_daily_limit(db_session, user.id, limit=2)


def test_counts_are_per_date(db_session, monkeypatch) -> None:
    """日付（JST）が変わるとカウントがリセットされ、翌日は独立してカウントされる。"""
    import app.services.agent.rate_limit as rl

    user = _make_user(db_session, "rl-date")

    fixed = {"today": date(2026, 7, 21)}
    monkeypatch.setattr(rl, "_today_jst", lambda: fixed["today"])

    assert enforce_daily_limit(db_session, user.id, limit=5) == 1
    assert enforce_daily_limit(db_session, user.id, limit=5) == 2
    # 翌日へ進めるとカウントが 1 に戻る
    fixed["today"] = date(2026, 7, 22)
    assert enforce_daily_limit(db_session, user.id, limit=5) == 1


def test_counts_are_per_user(db_session) -> None:
    """ユーザごとに独立（ユーザ A の消費がユーザ B の上限に影響しない）。"""
    user_a = _make_user(db_session, "rl-user-a")
    user_b = _make_user(db_session, "rl-user-b")
    for _ in range(3):
        enforce_daily_limit(db_session, user_a.id, limit=3)

    # B は A の消費に影響されず、1 回目から許可される
    assert enforce_daily_limit(db_session, user_b.id, limit=3) == 1


def test_limit_resolved_from_env(monkeypatch) -> None:
    """上限値は AGENT_DAILY_LIMIT（未設定時はデフォルト）から解決される。"""
    from app.core import env_keys
    from app.services.agent.rate_limit import DEFAULT_AGENT_DAILY_LIMIT, resolve_daily_limit

    monkeypatch.delenv(env_keys.AGENT_DAILY_LIMIT, raising=False)
    assert resolve_daily_limit() == DEFAULT_AGENT_DAILY_LIMIT

    monkeypatch.setenv(env_keys.AGENT_DAILY_LIMIT, "7")
    assert resolve_daily_limit() == 7

    # 不正値・非正値は既定値にフォールバック
    monkeypatch.setenv(env_keys.AGENT_DAILY_LIMIT, "abc")
    assert resolve_daily_limit() == DEFAULT_AGENT_DAILY_LIMIT
    monkeypatch.setenv(env_keys.AGENT_DAILY_LIMIT, "0")
    assert resolve_daily_limit() == DEFAULT_AGENT_DAILY_LIMIT
