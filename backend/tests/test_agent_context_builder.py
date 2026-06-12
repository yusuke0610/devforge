"""context_builder の単体テスト（GitHub/ブログ参照コンテキスト構築・圧縮・degrade）。

DB はモックしない（conftest の db_session fixture で実 SQLite を使う）。
"""

from datetime import date, timedelta

import pytest
from app.models import GitHubLinkCache, User
from app.models.blog import BlogAccount, BlogArticle, BlogArticleTag
from app.repositories import UserRepository
from app.services.agent.context_builder import (
    _LANGUAGES_TOP_N,
    _RECENT_ARTICLES_N,
    build_reference_context,
)


def _make_user(db_session, username: str) -> User:
    """テスト用ユーザーを作成して返す。"""
    repo = UserRepository(db_session)
    if not repo.get_by_username(username):
        repo.create(username, email=f"{username}@example.com")
        db_session.commit()
    user = repo.get_by_username(username)
    assert user is not None
    return user


def _make_github_cache(db_session, user_id: str, *, status: str = "completed", result: dict | None = None) -> GitHubLinkCache:
    """GitHubLinkCache を作成して DB に追加する。"""
    cache = GitHubLinkCache(
        user_id=user_id,
        status=status,
        result=result or {
            "username": "u",
            "repos_analyzed": 1,
            "unique_skills": 1,
            "analyzed_at": "2026-01-01",
            "languages": {"Python": 100000, "TypeScript": 50000, "Go": 30000},
            "contribution_calendars": [
                {
                    "year": 2025,
                    "total_contributions": 250,
                    "weeks": [
                        [{"date": "2025-06-01", "count": 3, "level": 2}],
                        [{"date": "2025-06-08", "count": 0, "level": 0}],
                    ],
                }
            ],
        },
    )
    db_session.add(cache)
    db_session.commit()
    return cache


def _make_blog_articles(db_session, user_id: str, count: int) -> list[BlogArticle]:
    """ブログアカウントと記事を count 件作成して返す。"""
    account = BlogAccount(user_id=user_id, platform="zenn", username="testblog")
    db_session.add(account)
    db_session.flush()
    articles = []
    for i in range(count):
        article = BlogArticle(
            account_id=account.id,
            external_id=f"article-{i}",
            title=f"技術記事 {i}",
            url=f"https://zenn.dev/testblog/{i}",
            likes_count=i * 2,
        )
        db_session.add(article)
        db_session.flush()
        tag = BlogArticleTag(article_id=article.id, sort_order=0, name="Python")
        db_session.add(tag)
        articles.append(article)
    db_session.commit()
    return articles


# --- スコープゲートのテスト ---


@pytest.mark.parametrize("scope", ["project", "experience"])
def test_reference_scopes_excluded(db_session, scope: str) -> None:
    """project / experience スコープでは参照コンテキストを返さない。"""
    user = _make_user(db_session, f"gate_{scope}")
    _make_github_cache(db_session, user.id)

    result = build_reference_context(db_session, user.id, scope)
    assert result is None


# --- GitHub コンテキストのテスト ---


def test_github_context_languages_top_n(db_session) -> None:
    """languages は上位 N 件を割合（%）に変換して返す。"""
    user = _make_user(db_session, "gh_lang")
    languages = {f"Lang{i}": (10 - i) * 10000 for i in range(8)}  # 8 言語
    _make_github_cache(
        db_session,
        user.id,
        result={
            "username": "u",
            "repos_analyzed": 1,
            "unique_skills": 1,
            "analyzed_at": "2026-01-01",
            "languages": languages,
            "contribution_calendars": [],
        },
    )

    result = build_reference_context(db_session, user.id, "career_summary")
    assert result is not None
    gh = result["github_context"]
    assert len(gh["languages_top5"]) == _LANGUAGES_TOP_N
    # 上位は Lang0（最大バイト数）
    assert gh["languages_top5"][0]["name"] == "Lang0"
    # 割合の合計は 100% を超えない（上位5件のみ）
    total_percent = sum(lang["percent"] for lang in gh["languages_top5"])
    assert total_percent <= 100.0


def test_github_context_weeks_discarded(db_session) -> None:
    """contributions_by_year には total のみ入り weeks は含まれない。"""
    user = _make_user(db_session, "gh_weeks")
    _make_github_cache(db_session, user.id)

    result = build_reference_context(db_session, user.id, "self_pr")
    assert result is not None
    contributions = result["github_context"]["contributions_by_year"]
    assert len(contributions) > 0
    for entry in contributions:
        assert "weeks" not in entry
        assert "year" in entry
        assert "total" in entry


def test_github_context_active_days_12m(db_session) -> None:
    """active_days_last_12_months は直近 365 日の count > 0 の日数を返す。"""
    user = _make_user(db_session, "gh_active")
    today = date.today()
    recent = (today - timedelta(days=10)).isoformat()
    old = (today - timedelta(days=400)).isoformat()
    _make_github_cache(
        db_session,
        user.id,
        result={
            "username": "u",
            "repos_analyzed": 1,
            "unique_skills": 1,
            "analyzed_at": "2026-01-01",
            "languages": {"Python": 1000},
            "contribution_calendars": [
                {
                    "year": today.year,
                    "total_contributions": 5,
                    "weeks": [
                        [{"date": recent, "count": 2, "level": 1}],  # 直近365日内、count > 0
                        [{"date": old, "count": 3, "level": 2}],      # 365日以前、対象外
                    ],
                }
            ],
        },
    )

    result = build_reference_context(db_session, user.id, "career_summary")
    assert result is not None
    assert result["github_context"]["active_days_last_12_months"] == 1


def test_github_context_status_processing_returns_none(db_session) -> None:
    """status が processing のキャッシュは None に degrade する。"""
    user = _make_user(db_session, "gh_proc")
    _make_github_cache(db_session, user.id, status="processing")

    result = build_reference_context(db_session, user.id, "career_summary")
    # github_context が無い（blog も無い）ので None
    assert result is None


def test_github_context_no_cache_returns_none(db_session) -> None:
    """GitHub キャッシュ未連携は github_context が省略され None になる。"""
    user = _make_user(db_session, "gh_nocache")

    result = build_reference_context(db_session, user.id, "career_summary")
    assert result is None


# --- ブログコンテキストのテスト ---


def test_blog_context_recent_articles_limit(db_session) -> None:
    """記事が N 件超でも recent_articles は上位 N 件に切り詰める。"""
    user = _make_user(db_session, "blog_limit")
    _make_blog_articles(db_session, user.id, _RECENT_ARTICLES_N + 1)

    result = build_reference_context(db_session, user.id, "career_summary")
    assert result is not None
    blog = result["blog_context"]
    assert len(blog["recent_articles"]) == _RECENT_ARTICLES_N
    assert "tech_article_count" in blog
    assert "avg_monthly_posts" in blog


def test_blog_context_no_articles_returns_none(db_session) -> None:
    """記事 0 件は blog_context が省略され None になる。"""
    user = _make_user(db_session, "blog_empty")

    result = build_reference_context(db_session, user.id, "career_summary")
    assert result is None


# --- degrade（DB 例外）のテスト ---


def test_github_context_db_error_degrades(db_session, monkeypatch) -> None:
    """DB 例外時は github_context を省略して処理を継続する（degrade）。"""
    user = _make_user(db_session, "gh_err")
    _make_github_cache(db_session, user.id)

    import app.services.agent.context_builder as cb

    def _raise(*a, **kw):
        raise RuntimeError("db error")

    monkeypatch.setattr(cb, "_build_github_context", _raise)
    result = build_reference_context(db_session, user.id, "career_summary")
    # _build_github_context が例外 → github_context は省略。blog も無いので None
    assert result is None


def test_blog_context_db_error_degrades(db_session, monkeypatch) -> None:
    """DB 例外時は blog_context を省略して処理を継続する（degrade）。"""
    user = _make_user(db_session, "blog_err")
    _make_github_cache(db_session, user.id)

    import app.services.agent.context_builder as cb

    def _raise(*a, **kw):
        raise RuntimeError("db error")

    monkeypatch.setattr(cb, "_build_blog_context", _raise)
    result = build_reference_context(db_session, user.id, "career_summary")
    # blog_context が省略されるが github_context は正常なので None にはならない
    assert result is not None
    assert "github_context" in result
    assert "blog_context" not in result
