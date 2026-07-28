"""routers/_shared.py の共通ヘルパーの単体テスト。

routers/agent.py と routers/github_link/endpoints.py の 2 箇所から呼ばれていた
日次レート制限 → 429 変換ロジックを ``enforce_agent_daily_limit`` に抽出した
（BE_report_20260728_2200.md High #3）。ここではその抽出後の関数自体を直接検証する
（DB はモックしない・実 SQLite セッション）。
"""

from typing import cast

import pytest
from app.core import env_keys
from app.repositories import UserRepository
from app.routers._shared import enforce_agent_daily_limit
from fastapi import HTTPException


def _make_user(db_session, username: str):
    repo = UserRepository(db_session)
    if not repo.get_by_username(username):
        repo.create(username, email=f"{username}@example.com")
        db_session.commit()
    user = repo.get_by_username(username)
    assert user is not None
    return user


def test_enforce_agent_daily_limit_allows_under_limit(db_session) -> None:
    """上限未満なら例外を出さずに正常終了する。"""
    user = _make_user(db_session, "shared-rl-under")

    enforce_agent_daily_limit(db_session, user.id)  # raise しないこと


def test_enforce_agent_daily_limit_raises_429_over_limit(db_session, monkeypatch) -> None:
    """上限超過時は 429 + AGENT_DAILY_LIMIT_EXCEEDED の HTTPException を送出する。"""
    monkeypatch.setenv(env_keys.AGENT_DAILY_LIMIT, "1")
    user = _make_user(db_session, "shared-rl-over")

    enforce_agent_daily_limit(db_session, user.id)  # 1 回目（上限ちょうど）は通る

    with pytest.raises(HTTPException) as excinfo:
        enforce_agent_daily_limit(db_session, user.id)

    assert excinfo.value.status_code == 429
    detail = cast(dict, excinfo.value.detail)
    assert detail["code"] == "AGENT_DAILY_LIMIT_EXCEEDED"
