"""
タスクハンドラの失敗パスを固定化するテスト。

CLAUDE.md の「タスクハンドラの『黙って return』は禁止」原則に基づき、
3 ハンドラ（github_analysis / blog_summarize / career_analysis）の以下分岐で
``NonRetryableError`` が必ず raise されることを assert する。

- payload に必須キー（user_id 等）が無い
- DB に対応するレコード（キャッシュ / 分析）が無い

worker は ``NonRetryableError`` を捕捉して ``dead_letter`` に遷移させるため、
silent return / RuntimeError では「completed」として観測される回帰バグを直接検知できる。
"""

from __future__ import annotations

import asyncio

import pytest
from app.repositories import UserRepository
from app.services.tasks.exceptions import NonRetryableError
from app.services.tasks.handlers.blog_summarize import BlogSummarizeHandler
from app.services.tasks.handlers.career_analysis import CareerAnalysisHandler
from app.services.tasks.handlers.github_analysis import GitHubAnalysisHandler
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


# ── BlogSummarizeHandler ──────────────────────────────────────


class TestBlogSummarizeHandlerFailures:
    """ブログサマリハンドラの失敗パス。"""

    def test_missing_user_id_raises_non_retryable(self, session_factory) -> None:
        """payload に user_id が無い → NonRetryableError。"""
        handler = BlogSummarizeHandler()
        with pytest.raises(NonRetryableError):
            _run(handler.run(session_factory, payload={}))

    def test_missing_cache_raises_non_retryable(
        self, db_session: Session, session_factory
    ) -> None:
        """user_id はあるが BlogSummaryCache が無い → NonRetryableError。"""
        user = _make_user(db_session, "blog-handler-no-cache")
        handler = BlogSummarizeHandler()
        with pytest.raises(NonRetryableError):
            _run(handler.run(session_factory, payload={"user_id": user.id}))


# ── CareerAnalysisHandler ─────────────────────────────────────


class TestCareerAnalysisHandlerFailures:
    """キャリア分析ハンドラの失敗パス。"""

    def test_missing_user_id_raises_non_retryable(self, session_factory) -> None:
        """user_id のみ欠落 → NonRetryableError。

        他の必須キー（record_id / target_position）は揃えた上で user_id だけ
        外し、user_id 欠落の検知のみを単独で固定化する。
        """
        handler = CareerAnalysisHandler()
        with pytest.raises(NonRetryableError):
            _run(
                handler.run(
                    session_factory,
                    payload={"record_id": 1, "target_position": "Backend"},
                )
            )

    def test_missing_record_id_raises_non_retryable(
        self, db_session: Session, session_factory
    ) -> None:
        """record_id のみ欠落 → NonRetryableError。

        user_id と target_position は揃えた上で record_id だけ外し、
        record_id 欠落の検知のみを単独で固定化する。
        """
        user = _make_user(db_session, "career-handler-no-record-id")
        handler = CareerAnalysisHandler()
        with pytest.raises(NonRetryableError):
            _run(
                handler.run(
                    session_factory,
                    payload={"user_id": user.id, "target_position": "Backend"},
                )
            )

    def test_missing_record_raises_non_retryable(
        self, db_session: Session, session_factory
    ) -> None:
        """user_id / record_id はあるが CareerAnalysis が DB に無い → NonRetryableError。"""
        user = _make_user(db_session, "career-handler-no-record")
        handler = CareerAnalysisHandler()
        with pytest.raises(NonRetryableError):
            _run(
                handler.run(
                    session_factory,
                    payload={
                        "user_id": user.id,
                        "record_id": 999999,
                        "target_position": "Backend",
                    },
                )
            )


# ── GitHubAnalysisHandler ─────────────────────────────────────


class TestGithubAnalysisHandlerFailures:
    """GitHub 分析ハンドラの失敗パス。"""

    def test_missing_user_id_raises_non_retryable(self, session_factory) -> None:
        """payload に user_id が無い → NonRetryableError。"""
        handler = GitHubAnalysisHandler()
        with pytest.raises(NonRetryableError):
            _run(handler.run(session_factory, payload={}))

    def test_missing_cache_raises_non_retryable(
        self, db_session: Session, session_factory
    ) -> None:
        """user_id はあるが GitHubAnalysisCache が無い → NonRetryableError。

        現状は RuntimeError を raise しており worker のリトライ対象になってしまうため、
        テストとしては失敗するはず（fix 後に通過）。
        """
        user = _make_user(db_session, "gh-handler-no-cache")
        handler = GitHubAnalysisHandler()
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
