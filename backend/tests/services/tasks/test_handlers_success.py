"""
タスクハンドラの正常系パスを worker シムを介さず直接固定化するテスト。

`tests/test_worker/` 配下では `_run_*` シム経由のテストが網羅されている。
こちらは「ハンドラ実装を直接呼んでも同じく status=completed に遷移すること」を
最小限のスモークテストで守る。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import BlogSummaryCache
from app.models.career_analysis import CareerAnalysis
from app.repositories import UserRepository
from app.services.tasks.handlers.blog_summarize import BlogSummarizeHandler
from app.services.tasks.handlers.career_analysis import CareerAnalysisHandler
from sqlalchemy.orm import Session


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_user(db: Session, username: str):
    return UserRepository(db).create(
        username, hashed_password=None, email=f"{username}@test.com",
    )


class TestBlogSummarizeHandlerSuccess:
    """BlogSummarizeHandler.run を直接呼び出す正常系。"""

    def test_run_completes_and_persists_summary(
        self, db_session: Session, session_factory
    ) -> None:
        user = _make_user(db_session, "handler-blog-success")
        cache = BlogSummaryCache(user_id=user.id, status="pending")
        db_session.add(cache)
        db_session.commit()

        # 記事 1 件を持つモック repo
        art = MagicMock()
        art.title = "テスト記事"
        art.url = "https://example.com/a"
        art.published_at = "2024-01-01"
        art.likes_count = 1
        art.summary = "本文"
        art.tags = ["python"]
        art.platform = "zenn"
        mock_repo = MagicMock()
        mock_repo.list_by_user.return_value = [art]

        mock_llm = MagicMock()
        mock_llm.check_available = AsyncMock(return_value=True)

        with (
            patch(
                "app.services.tasks.handlers.blog_summarize.BlogArticleRepository",
                return_value=mock_repo,
            ),
            patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm),
            patch(
                "app.services.intelligence.llm_summarizer.summarize_blog_articles",
                new_callable=AsyncMock,
                return_value="完成版サマリ",
            ),
        ):
            handler = BlogSummarizeHandler()
            _run(handler.run(session_factory, {"user_id": user.id}))

        db_session.expire_all()
        db_session.refresh(cache)
        assert cache.status == "completed"
        assert cache.summary == "完成版サマリ"
        assert cache.completed_at is not None
        assert cache.expires_at is not None


class TestCareerAnalysisHandlerSuccess:
    """CareerAnalysisHandler.run を直接呼び出す正常系。"""

    def test_run_completes_and_persists_result(
        self, db_session: Session, session_factory
    ) -> None:
        user = _make_user(db_session, "handler-career-success")
        analysis = CareerAnalysis(
            user_id=user.id,
            version=1,
            target_position="Backend",
            status="pending",
        )
        db_session.add(analysis)
        db_session.commit()

        mock_llm = MagicMock()
        fake_result = {
            "growth_summary": "",
            "tech_stack": {"top": [], "summary": ""},
            "strengths": [],
            "career_paths": [],
            "action_items": [],
        }

        # 新ハンドラは collect_career_inputs + generate_career_analysis を分けて呼ぶ
        with (
            patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm),
            patch(
                "app.services.career_analysis.builder.generate_career_analysis",
                new_callable=AsyncMock,
                return_value=fake_result,
            ),
        ):
            handler = CareerAnalysisHandler()
            _run(
                handler.run(
                    session_factory,
                    {
                        "user_id": user.id,
                        "record_id": analysis.id,
                        "target_position": "Backend",
                    },
                )
            )

        db_session.expire_all()
        db_session.refresh(analysis)
        assert analysis.status == "completed"
        assert analysis.result_json is not None
        assert analysis.completed_at is not None
