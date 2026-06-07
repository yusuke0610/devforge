"""_run_github_link の単体テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import GitHubLinkCache
from app.repositories import UserRepository
from app.services.tasks.worker import _run_github_link
from sqlalchemy.orm import Session

from ._helpers import run_sync as _run


class TestRunGithubAnalysis:
    def _make_user_and_cache(self, db: Session, username="gh-user"):
        user = UserRepository(db).create(
            username,
            email=f"{username}@test.com",
        )
        cache = GitHubLinkCache(user_id=user.id, status="pending")
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
            )
        ]

    def test_status_transitions_to_completed(self, db_session: Session, session_factory):
        """正常系: status が completed に遷移すること。"""
        user, cache = self._make_user_and_cache(db_session)
        repos = self._sample_repos()

        with (
            patch(
                "app.services.intelligence.github_link_service.collect_repos",
                new_callable=AsyncMock,
                return_value=repos,
            ),
            patch(
                "app.services.intelligence.github_link_service.fetch_all_contribution_calendars",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.progress_service.set_progress",
                new_callable=AsyncMock,
            ),
            patch(
                "app.services.intelligence.github_link_service.decrypt_field",
                return_value="token123",
            ),
        ):
            _run(
                _run_github_link(
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
        assert cache.result is not None
        assert cache.completed_at is not None

    def test_completed_persists_mapped_result_content(
        self, db_session: Session, session_factory
    ):
        """フェーズC: 成功時に map_pipeline_result の出力が cache.result へ
        そのまま永続化され、error/warning がクリアされること（内容まで検証）。"""
        from app.schemas.github_link import ContributionCalendar, ContributionDay

        user, cache = self._make_user_and_cache(db_session, "content-user")
        # 前回失敗の痕跡が成功時にクリアされることも併せて確認する
        cache.error_message = "前回の失敗"
        cache.warning_message = "前回の警告"
        db_session.commit()

        repos = self._sample_repos()
        # コントリビューション取得が成功するケース。これにより新たな警告は出ず、
        # 前回の warning_message がクリアされることを純粋に検証できる。
        calendars = [
            ContributionCalendar(
                year=2024,
                total_contributions=7,
                weeks=[[ContributionDay(date="2024-03-01", count=3, level=2)]],
            )
        ]
        sentinel_result = {
            "skills": [{"name": "Python", "score": 80}],
            "summary": "集計結果",
        }
        mapped = MagicMock()
        mapped.model_dump.return_value = sentinel_result

        with (
            patch(
                "app.services.intelligence.github_link_service.collect_repos",
                new_callable=AsyncMock,
                return_value=repos,
            ),
            patch(
                "app.services.intelligence.github_link_service.fetch_all_contribution_calendars",
                new_callable=AsyncMock,
                return_value=calendars,
            ),
            patch("app.services.progress_service.set_progress", new_callable=AsyncMock),
            patch(
                "app.services.intelligence.github_link_service.decrypt_field",
                return_value="token123",
            ),
            patch(
                "app.services.intelligence.github_link_service.aggregate_intelligence",
                return_value=MagicMock(),
            ),
            patch(
                "app.services.intelligence.github_link_service.map_pipeline_result",
                return_value=mapped,
            ),
        ):
            _run(
                _run_github_link(
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
        # フェーズCで mapper の出力がそのまま書き戻されていること
        assert cache.result == sentinel_result
        mapped.model_dump.assert_called_once()
        # 成功時は前回の error/warning がクリアされること
        assert cache.error_message is None
        assert cache.warning_message is None
        assert cache.completed_at is not None

    def test_contribution_calendar_persisted_in_result(
        self, db_session: Session, session_factory
    ):
        """コントリビューションカレンダーが取得できた場合、result に格納され
        warning_message が立たないこと。"""
        from app.schemas.github_link import ContributionCalendar, ContributionDay

        user, cache = self._make_user_and_cache(db_session, "calendar-user")
        repos = self._sample_repos()
        calendars = [
            ContributionCalendar(
                year=2024,
                total_contributions=7,
                weeks=[[ContributionDay(date="2024-03-01", count=3, level=2)]],
            )
        ]

        with (
            patch(
                "app.services.intelligence.github_link_service.collect_repos",
                new_callable=AsyncMock,
                return_value=repos,
            ),
            patch(
                "app.services.intelligence.github_link_service.fetch_all_contribution_calendars",
                new_callable=AsyncMock,
                return_value=calendars,
            ),
            patch("app.services.progress_service.set_progress", new_callable=AsyncMock),
            patch(
                "app.services.intelligence.github_link_service.decrypt_field",
                return_value="token123",
            ),
        ):
            _run(
                _run_github_link(
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
        assert cache.result is not None
        assert cache.result["contribution_calendars"][0]["year"] == 2024
        assert cache.result["contribution_calendars"][0]["total_contributions"] == 7
        assert cache.result["contribution_calendars"][0]["weeks"][0][0]["level"] == 2
        assert cache.warning_message is None

    def test_contribution_fetch_failure_sets_warning(
        self, db_session: Session, session_factory
    ):
        """コントリビューション取得失敗（None）でも連携は completed のままで、
        warning_message が立つこと。"""
        user, cache = self._make_user_and_cache(db_session, "warn-user")
        repos = self._sample_repos()

        with (
            patch(
                "app.services.intelligence.github_link_service.collect_repos",
                new_callable=AsyncMock,
                return_value=repos,
            ),
            patch(
                "app.services.intelligence.github_link_service.fetch_all_contribution_calendars",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("app.services.progress_service.set_progress", new_callable=AsyncMock),
            patch(
                "app.services.intelligence.github_link_service.decrypt_field",
                return_value="token123",
            ),
        ):
            _run(
                _run_github_link(
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
        assert cache.result is not None
        assert cache.result["contribution_calendars"] == []
        assert cache.warning_message is not None

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
                "app.services.intelligence.github_link_service.collect_repos",
                side_effect=_fake_collect,
            ),
            patch("app.services.progress_service.set_progress", new_callable=AsyncMock),
            patch(
                "app.services.intelligence.github_link_service.decrypt_field",
                return_value=None,
            ),
        ):
            _run(
                _run_github_link(
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

        user, cache = self._make_user_and_cache(db_session, "notfound")

        with (
            patch(
                "app.services.intelligence.github_link_service.collect_repos",
                new_callable=AsyncMock,
                side_effect=GitHubUserNotFoundError("notfound"),
            ),
            patch("app.services.progress_service.set_progress", new_callable=AsyncMock),
            patch(
                "app.services.intelligence.github_link_service.decrypt_field",
                return_value=None,
            ),
        ):
            with pytest.raises(GitHubUserNotFoundError):
                _run(
                    _run_github_link(
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
                _run_github_link(
                    session_factory,
                    {
                        "user_id": "nonexistent-user-id",
                        "github_username": "nobody",
                        "github_token": None,
                        "include_forks": False,
                    },
                )
            )
