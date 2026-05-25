"""_run_github_analysis の単体テスト。"""

from unittest.mock import AsyncMock, patch

import pytest
from app.models import GitHubAnalysisCache
from app.repositories import UserRepository
from app.services.tasks.worker import _run_github_analysis
from sqlalchemy.orm import Session

from ._helpers import run_sync as _run


class TestRunGithubAnalysis:
    def _make_user_and_cache(self, db: Session, username="github:gh-user"):
        user = UserRepository(db).create(
            username,
            hashed_password=None,
            email=f"{username}@test.com",
        )
        cache = GitHubAnalysisCache(user_id=user.id, status="pending")
        db.add(cache)
        db.commit()
        return user, cache

    def _sample_repos(self):
        from app.services.intelligence.github_collector import RepoData

        return [
            RepoData(
                name="repo1",
                owner="gh-user",
                description="",
                languages={"Python": 10000},
                topics=["fastapi"],
                created_at="2023-01-01T00:00:00Z",
                pushed_at="2024-01-01T00:00:00Z",
                fork=False,
                stargazers_count=0,
                default_branch="main",
                dependencies=[],
                root_files=[],
                detected_frameworks=[],
                detected_devtools=[],
                detected_infras=[],
            )
        ]

    def test_status_transitions_to_completed(self, db_session: Session, session_factory):
        """正常系: status が completed に遷移すること。"""
        user, cache = self._make_user_and_cache(db_session)
        repos = self._sample_repos()

        with (
            patch(
                "app.services.intelligence.github_analysis_service.collect_repos",
                new_callable=AsyncMock,
                return_value=repos,
            ),
            patch(
                "app.services.progress_service.set_progress",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.intelligence.github_analysis_service.decrypt_field",
                return_value="token123",
            ),
        ):
            _run(
                _run_github_analysis(
                    session_factory,
                    {
                        "user_id": user.id,
                        "github_username": "gh-user",
                        "github_token": "encrypted_token",
                        "include_forks": False,
                    },
                )
            )

        db_session.refresh(cache)
        assert cache.status == "completed"
        assert cache.analysis_result is not None
        assert cache.completed_at is not None

    def test_status_transitions_to_processing_at_start(
        self, db_session: Session, session_factory
    ):
        """タスク開始時に status が processing に更新されること。"""
        user, cache = self._make_user_and_cache(db_session)
        repos = self._sample_repos()

        processing_status = []

        async def _fake_collect(**kwargs):
            db_session.expire_all()
            db_session.refresh(cache)
            processing_status.append(cache.status)
            return repos

        with (
            patch(
                "app.services.intelligence.github_analysis_service.collect_repos",
                side_effect=_fake_collect,
            ),
            patch("app.services.progress_service.set_progress", new_callable=AsyncMock),
            patch(
                "app.services.intelligence.github_analysis_service.decrypt_field",
                return_value=None,
            ),
        ):
            _run(
                _run_github_analysis(
                    session_factory,
                    {
                        "user_id": user.id,
                        "github_username": "gh-user",
                        "github_token": None,
                        "include_forks": False,
                    },
                )
            )

        assert "processing" in processing_status

    def test_github_user_not_found_sets_dead_letter(
        self, db_session: Session, session_factory
    ):
        """GitHubUserNotFoundError 発生時に status が dead_letter になること。"""
        from app.services.intelligence.github.api_client import GitHubUserNotFoundError

        user, cache = self._make_user_and_cache(db_session, "github:notfound")

        with (
            patch(
                "app.services.intelligence.github_analysis_service.collect_repos",
                new_callable=AsyncMock,
                side_effect=GitHubUserNotFoundError("notfound"),
            ),
            patch("app.services.progress_service.set_progress", new_callable=AsyncMock),
            patch(
                "app.services.intelligence.github_analysis_service.decrypt_field",
                return_value=None,
            ),
        ):
            with pytest.raises(GitHubUserNotFoundError):
                _run(
                    _run_github_analysis(
                        session_factory,
                        {
                            "user_id": user.id,
                            "github_username": "notfound",
                            "github_token": None,
                            "include_forks": False,
                        },
                    )
                )

        db_session.refresh(cache)
        assert cache.status == "dead_letter"

    def test_no_cache_raises_non_retryable(self, session_factory):
        """キャッシュが見つからない場合、NonRetryableError が送出されること。

        worker 側で ``dead_letter`` 遷移と通知発行を行わせる契約。
        """
        from app.services.tasks.exceptions import NonRetryableError

        with pytest.raises(NonRetryableError):
            _run(
                _run_github_analysis(
                    session_factory,
                    {
                        "user_id": "nonexistent-user-id",
                        "github_username": "nobody",
                        "github_token": None,
                        "include_forks": False,
                    },
                )
            )
