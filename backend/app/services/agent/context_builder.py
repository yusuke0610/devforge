"""Agent チャット用の参照コンテキスト構築（GitHub/ブログ分析サマリー）。

DB アクセスはこのモジュールに閉じ込める。chat_service は DB に触れない。
GitHub/ブログは career_summary / self_pr スコープのみに付与し、
project / experience では None を返す（スコープゲート）。

参照データの取得失敗（未連携・processing 中・記事 0 件含む）は
チャット本体を落とさずコンテキスト省略（degrade）で吸収する。
"""

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from ...models.cache import GitHubLinkCache
from ...repositories.blog import BlogArticleRepository
from ...services.blog.scorer import blog_articles_to_score_dicts, calculate_blog_score

logger = logging.getLogger(__name__)

# GitHub/ブログコンテキストを付与するスコープ
_REFERENCE_SCOPES: frozenset[str] = frozenset({"career_summary", "self_pr"})

# 圧縮契約の上限値（ADR-0010「コンテキスト圧縮」）
_LANGUAGES_TOP_N = 5
_CONTRIBUTIONS_YEARS = 5
_RECENT_ARTICLES_N = 5
_RECENT_ARTICLE_TAGS_N = 5


def build_reference_context(db: Session, user_id: str, scope: str) -> dict | None:
    """career_summary / self_pr スコープ向けに GitHub/ブログ参照コンテキストを構築する。

    スコープが対象外の場合・データが未取得の場合はいずれも None を返す。
    取得失敗は warning ログを出して None に degrade し、チャット本体への影響を防ぐ。
    DB は SELECT のみ。commit/flush/add は行わない。
    """
    if scope not in _REFERENCE_SCOPES:
        return None

    result: dict = {}

    try:
        github_ctx = _build_github_context(db, user_id)
    except Exception:
        logger.warning("GitHub コンテキストの取得に失敗（省略）", exc_info=True)
        github_ctx = None
    if github_ctx:
        result["github_context"] = github_ctx

    try:
        blog_ctx = _build_blog_context(db, user_id)
    except Exception:
        logger.warning("ブログコンテキストの取得に失敗（省略）", exc_info=True)
        blog_ctx = None
    if blog_ctx:
        result["blog_context"] = blog_ctx

    return result if result else None


def _build_github_context(db: Session, user_id: str) -> dict | None:
    """GitHubLinkCache から圧縮済み GitHub コンテキストを生成する。"""
    try:
        cache = db.query(GitHubLinkCache).filter_by(user_id=user_id).first()
        if not cache or cache.status != "completed" or not cache.result:
            return None

        result = cache.result
        languages_raw: dict[str, int] = result.get("languages") or {}
        calendars: list[dict] = result.get("contribution_calendars") or []

        # 言語上位 N 件を割合（%）に変換（生バイト数より LLM が解釈しやすい）
        total_bytes = sum(languages_raw.values()) or 1
        languages_top = sorted(languages_raw.items(), key=lambda x: x[1], reverse=True)[
            :_LANGUAGES_TOP_N
        ]
        languages = [
            {"name": lang, "percent": round(b / total_bytes * 100, 1)}
            for lang, b in languages_top
        ]

        # 年別コントリビューション（直近 N 年分。weeks は捨てる）
        sorted_calendars = sorted(calendars, key=lambda c: c.get("year", 0), reverse=True)
        contributions_by_year = [
            {"year": c["year"], "total": c["total_contributions"]}
            for c in sorted_calendars[:_CONTRIBUTIONS_YEARS]
            if "year" in c and "total_contributions" in c
        ]

        # 直近 12 ヶ月の活動日数
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        active_days = 0
        for cal in calendars:
            for week in cal.get("weeks") or []:
                for day in week:
                    if isinstance(day, dict) and day.get("date", "") >= cutoff:
                        if (day.get("count") or 0) > 0:
                            active_days += 1

        return {
            "languages_top5": languages,
            "contributions_by_year": contributions_by_year,
            "active_days_last_12_months": active_days,
        }
    except Exception:
        logger.warning("GitHub コンテキストの取得に失敗（省略）", exc_info=True)
        return None


def _build_blog_context(db: Session, user_id: str) -> dict | None:
    """BlogArticle から圧縮済みブログコンテキストを生成する。"""
    try:
        repo = BlogArticleRepository(db, user_id)
        articles = repo.list_by_user()
        if not articles:
            return None

        score = calculate_blog_score(blog_articles_to_score_dicts(articles))

        # 直近 N 件の記事（list_by_user は published_at 降順保証）
        recent_articles = [
            {
                "title": a.title,
                "tags": a.tags[:_RECENT_ARTICLE_TAGS_N],
                # published_at は format_iso_date 済みの str（または None）を返すプロパティ。
                # ここで .isoformat() を呼ぶと str に対する呼び出しで AttributeError になる。
                "published_at": a.published_at,
            }
            for a in articles[:_RECENT_ARTICLES_N]
        ]

        return {
            "tech_article_count": score.tech_article_count,
            "total_article_count": score.total_article_count,
            "avg_monthly_posts": score.avg_monthly_posts,
            "avg_likes": score.avg_likes,
            "recent_articles": recent_articles,
        }
    except Exception:
        logger.warning("ブログコンテキストの取得に失敗（省略）", exc_info=True)
        return None
