"""worker タイムアウト伝播のテスト。

asyncio.TimeoutError が _run_* シムから素通しで上位へ届き、
status は processing のまま（dead_letter への遷移は execute_task 層の責務）
であることを確認する。``_mark_dead_letter`` の動作は ``test_worker_extended.py``
側でカバー済み。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import BlogSummaryCache, GitHubAnalysisCache
from app.repositories import UserRepository
from app.services.tasks.worker import _run_blog_summarize, _run_github_analysis
from sqlalchemy.orm import Session


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_github_analysis_timeout_propagates(db_session: Session, session_factory) -> None:
    """collect_repos で asyncio.TimeoutError が発生した場合に例外が伝播することを確認する。"""
    user = UserRepository(db_session).create(
        "github:timeout-user",
        hashed_password=None,
        email="timeout@example.com",
    )
    cache = GitHubAnalysisCache(user_id=user.id, status="pending")
    db_session.add(cache)
    db_session.commit()

    with (
        patch(
            "app.services.intelligence.github_analysis_service.collect_repos",
            new_callable=AsyncMock,
            side_effect=asyncio.TimeoutError,
        ),
        patch(
            "app.services.progress_service.set_progress",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(asyncio.TimeoutError):
            _run(
                _run_github_analysis(
                    session_factory,
                    {
                        "user_id": user.id,
                        "github_username": "timeout-user",
                        "github_token": None,
                        "include_forks": False,
                    },
                )
            )

    db_session.expire_all()
    db_session.refresh(cache)
    # ハンドラは TimeoutError を再 raise するだけ（dead_letter 遷移は execute_task 層）
    assert cache.status == "processing"


def test_blog_summarize_timeout_propagates(db_session: Session, session_factory) -> None:
    """ブログサマリ生成で asyncio.TimeoutError が発生した場合に例外が伝播することを確認する。"""
    user = UserRepository(db_session).create(
        "blog-timeout-user",
        hashed_password=None,
        email="blogtimeout@example.com",
    )
    cache = BlogSummaryCache(user_id=user.id, status="pending")
    db_session.add(cache)
    db_session.commit()

    mock_llm = MagicMock()
    mock_llm.check_available = AsyncMock(return_value=True)

    # DB に記事がないと worker が early return するため、記事リストをモックで返す
    mock_article = MagicMock()
    mock_article.title = "テスト記事"
    mock_article.url = "https://example.com"
    mock_article.published_at = "2026-01-01"
    mock_article.likes_count = 0
    mock_article.summary = ""
    mock_article.tags = []
    mock_article.platform = "zenn"

    with patch(
        "app.services.intelligence.llm.get_llm_client",
        return_value=mock_llm,
    ):
        with patch(
            "app.services.tasks.handlers.blog_summarize.BlogArticleRepository",
        ) as mock_repo_cls:
            mock_repo_cls.return_value.list_by_user.return_value = [mock_article]
            with patch(
                "app.services.intelligence.llm_summarizer.summarize_blog_articles",
                new_callable=AsyncMock,
                side_effect=asyncio.TimeoutError,
            ):
                with pytest.raises(asyncio.TimeoutError):
                    _run(
                        _run_blog_summarize(
                            session_factory,
                            {"user_id": user.id},
                        )
                    )

    db_session.expire_all()
    db_session.refresh(cache)
    assert cache.status == "processing"
