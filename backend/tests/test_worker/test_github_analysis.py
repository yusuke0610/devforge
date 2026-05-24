"""_run_github_analysis と _generate_advice_if_available の単体テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import GitHubAnalysisCache
from app.repositories import UserRepository
from app.services.intelligence.github_analysis_service import (
    _generate_advice_if_available,
)
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
                "app.services.intelligence.github_analysis_service.get_llm_client",
                return_value=MagicMock(check_available=AsyncMock(return_value=False)),
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
                "app.services.intelligence.github_analysis_service.get_llm_client",
                return_value=MagicMock(check_available=AsyncMock(return_value=False)),
            ),
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


class TestGenerateAdviceIfAvailable:
    def _analysis(self):
        return {
            "repos_analyzed": 5,
            "languages": {"Python": 50000},
            "position_scores": {
                "backend": 70,
                "frontend": 20,
                "fullstack": 45,
                "sre": 25,
                "cloud": 15,
                "missing_skills": [],
            },
        }

    def test_llm_unavailable_returns_none(self):
        """LLM が利用不可の場合 (None, False) を返すこと。"""
        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(return_value=False)

        with patch(
            "app.services.intelligence.github_analysis_service.get_llm_client",
            return_value=mock_llm,
        ):
            result = _run(_generate_advice_if_available(self._analysis()))

        assert result == (None, False)

    def test_llm_available_returns_advice(self):
        """LLM が利用可能の場合、(アドバイス文字列, False) を返すこと。"""
        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(return_value=True)

        with (
            patch(
                "app.services.intelligence.github_analysis_service.get_llm_client",
                return_value=mock_llm,
            ),
            patch(
                "app.services.intelligence.github_analysis_service.generate_learning_advice",
                new_callable=AsyncMock,
                return_value="学習アドバイスです",
            ),
        ):
            result = _run(_generate_advice_if_available(self._analysis()))

        assert result == ("学習アドバイスです", False)

    def test_llm_retryable_error_returns_warning(self):
        """LLM が想定内の RetryableError を送出した場合 (None, True) を返し例外を握りつぶすこと。"""
        from app.services.tasks.exceptions import RetryableError

        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(side_effect=RetryableError("LLM 一時障害"))

        with patch(
            "app.services.intelligence.github_analysis_service.get_llm_client",
            return_value=mock_llm,
        ):
            result = _run(_generate_advice_if_available(self._analysis()))

        assert result == (None, True)

    def test_llm_unexpected_exception_propagates(self):
        """LLM が予期しない例外を送出した場合は再送出されること（プログラミングエラー検知のため）。"""
        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(side_effect=Exception("LLM クラッシュ"))

        with patch(
            "app.services.intelligence.github_analysis_service.get_llm_client",
            return_value=mock_llm,
        ):
            with pytest.raises(Exception, match="LLM クラッシュ"):
                _run(_generate_advice_if_available(self._analysis()))

    def test_no_position_scores_returns_none(self):
        """position_scores が None の場合 (None, False) を返すこと。"""
        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(return_value=True)

        with patch(
            "app.services.intelligence.github_analysis_service.get_llm_client",
            return_value=mock_llm,
        ):
            result = _run(_generate_advice_if_available({"repos_analyzed": 5}))

        assert result == (None, False)
