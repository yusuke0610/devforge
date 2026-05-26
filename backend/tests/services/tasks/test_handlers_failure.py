"""
タスクハンドラの失敗パスを固定化するテスト。

CLAUDE.md の「タスクハンドラの『黙って return』は禁止」原則に基づき、
github_link ハンドラの以下分岐で
``NonRetryableError`` が必ず raise されることを assert する。

- payload に必須キー（user_id 等）が無い
- DB に対応するレコード（キャッシュ）が無い

worker は ``NonRetryableError`` を捕捉して ``dead_letter`` に遷移させるため、
silent return / RuntimeError では「completed」として観測される回帰バグを直接検知できる。
"""

from __future__ import annotations

import asyncio

import pytest
from app.repositories import UserRepository
from app.services.tasks.exceptions import NonRetryableError
from app.services.tasks.handlers.github_link import GitHubLinkHandler
from sqlalchemy.orm import Session


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_user(db: Session, username: str):
    """テスト用ユーザーを作成する。"""
    return UserRepository(db).create(
        username,
        hashed_password=None,
        email=f"{username}@test.com",
    )


# ── GitHubLinkHandler ─────────────────────────────────────


class TestGithubAnalysisHandlerFailures:
    """GitHub 連携ハンドラの失敗パス。"""

    def test_missing_user_id_raises_non_retryable(self, session_factory) -> None:
        """payload に user_id が無い → NonRetryableError。"""
        handler = GitHubLinkHandler()
        with pytest.raises(NonRetryableError):
            _run(handler.run(session_factory, payload={}))

    def test_missing_cache_raises_non_retryable(
        self, db_session: Session, session_factory
    ) -> None:
        """user_id はあるが GitHubLinkCache が無い → NonRetryableError。

        現状は RuntimeError を raise しており worker のリトライ対象になってしまうため、
        テストとしては失敗するはず（fix 後に通過）。
        """
        user = _make_user(db_session, "gh-handler-no-cache")
        handler = GitHubLinkHandler()
        with pytest.raises(NonRetryableError):
            _run(
                handler.run(
                    session_factory,
                    payload={
                        "user_id": user.id,
                        "github_username": "ghuser",
                        "include_forks": False,
                    },
                )
            )
