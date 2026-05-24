"""_run_blog_summarize の単体テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import BlogSummaryCache
from app.repositories import UserRepository
from app.services.tasks.worker import _run_blog_summarize
from sqlalchemy.orm import Session

from ._helpers import run_sync as _run


class TestRunBlogSummarize:
    def _make_user_and_cache(self, db: Session, username="blog-worker-user"):
        user = UserRepository(db).create(
            username,
            hashed_password=None,
            email=f"{username}@test.com",
        )
        cache = BlogSummaryCache(user_id=user.id, status="pending")
        db.add(cache)
        db.commit()
        return user, cache

    def _make_mock_repo(self, articles=None):
        """BlogArticleRepository のモックを返す。articles 省略時は記事1件。"""
        art = MagicMock()
        art.title = "テスト記事"
        art.url = "https://zenn.dev/test/articles/test"
        art.published_at = "2024-01-01"
        art.likes_count = 5
        art.summary = "要約"
        art.tags = ["Python"]
        art.platform = "zenn"
        mock_repo = MagicMock()
        mock_repo.list_by_user.return_value = articles if articles is not None else [art]
        return mock_repo

    def test_success_status_completed(self, db_session: Session, session_factory):
        """正常系: LLM が要約を返し、status が completed になること。"""
        user, cache = self._make_user_and_cache(db_session)
        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(return_value=True)

        with (
            patch(
                "app.services.tasks.handlers.blog_summarize.BlogArticleRepository",
                return_value=self._make_mock_repo(),
            ),
            patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm),
            patch(
                "app.services.intelligence.llm_summarizer.summarize_blog_articles",
                new_callable=AsyncMock,
                return_value="AI 要約テキスト",
            ),
        ):
            _run(
                _run_blog_summarize(
                    session_factory,
                    {"user_id": user.id},
                )
            )

        db_session.refresh(cache)
        assert cache.status == "completed"
        assert cache.summary == "AI 要約テキスト"
        assert cache.completed_at is not None
        assert cache.expires_at is not None

    def test_llm_unavailable_sets_dead_letter(self, db_session: Session, session_factory):
        """LLM が利用不可の場合に status が dead_letter になること。"""
        user, cache = self._make_user_and_cache(db_session, "blog-nollm")
        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(return_value=False)

        with (
            patch(
                "app.services.tasks.handlers.blog_summarize.BlogArticleRepository",
                return_value=self._make_mock_repo(),
            ),
            patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm),
        ):
            _run(
                _run_blog_summarize(
                    session_factory,
                    {"user_id": user.id},
                )
            )

        db_session.refresh(cache)
        assert cache.status == "dead_letter"
        assert cache.error_message is not None

    def test_empty_summary_sets_dead_letter(self, db_session: Session, session_factory):
        """LLM が空文字を返した場合に status が dead_letter になること。"""
        user, cache = self._make_user_and_cache(db_session, "blog-empty")
        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(return_value=True)

        with (
            patch(
                "app.services.tasks.handlers.blog_summarize.BlogArticleRepository",
                return_value=self._make_mock_repo(),
            ),
            patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm),
            patch(
                "app.services.intelligence.llm_summarizer.summarize_blog_articles",
                new_callable=AsyncMock,
                return_value="",
            ),
        ):
            _run(
                _run_blog_summarize(
                    session_factory,
                    {"user_id": user.id},
                )
            )

        db_session.refresh(cache)
        assert cache.status == "dead_letter"

    def test_no_articles_sets_dead_letter(self, db_session: Session, session_factory):
        """記事が 0 件の場合に status が dead_letter になること。"""
        user, cache = self._make_user_and_cache(db_session, "blog-no-articles")

        with patch(
            "app.services.tasks.handlers.blog_summarize.BlogArticleRepository",
            return_value=self._make_mock_repo(articles=[]),
        ):
            _run(
                _run_blog_summarize(
                    session_factory,
                    {"user_id": user.id},
                )
            )

        db_session.refresh(cache)
        assert cache.status == "dead_letter"
        assert cache.error_message == "分析対象の記事がありません"

    def test_no_cache_raises_non_retryable(self, session_factory):
        """キャッシュが見つからない場合、NonRetryableError を送出すること。"""
        from app.services.tasks.exceptions import NonRetryableError

        with pytest.raises(NonRetryableError):
            _run(
                _run_blog_summarize(
                    session_factory,
                    {"user_id": "ghost-user"},
                )
            )

    def test_status_set_to_processing_before_llm_call(
        self, db_session: Session, session_factory
    ):
        """LLM 呼び出し前に status が processing に更新されること。"""
        user, cache = self._make_user_and_cache(db_session, "blog-processing")
        processing_status = []
        mock_llm = MagicMock()

        async def _fake_check_available():
            db_session.expire_all()
            db_session.refresh(cache)
            processing_status.append(cache.status)
            return False

        mock_llm.check_available = _fake_check_available

        with (
            patch(
                "app.services.tasks.handlers.blog_summarize.BlogArticleRepository",
                return_value=self._make_mock_repo(),
            ),
            patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm),
        ):
            _run(
                _run_blog_summarize(
                    session_factory,
                    {"user_id": user.id},
                )
            )

        assert "processing" in processing_status
