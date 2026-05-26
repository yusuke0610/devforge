from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..core.date_utils import parse_iso_date
from ..models import BlogAccount, BlogArticle, BlogArticleTag


class BlogAccountRepository:
    """ブログ連携アカウントリポジトリ。"""

    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id

    def list_by_user(self) -> list[BlogAccount]:
        statement = (
            select(BlogAccount)
            .where(BlogAccount.user_id == self.user_id)
            .order_by(BlogAccount.created_at)
        )
        return list(self.db.scalars(statement).all())

    def get_by_id(self, account_id: str) -> BlogAccount | None:
        statement = (
            select(BlogAccount)
            .where(BlogAccount.id == account_id)
            .where(BlogAccount.user_id == self.user_id)
        )
        return self.db.scalar(statement)

    def get_by_platform(self, platform: str) -> BlogAccount | None:
        statement = (
            select(BlogAccount)
            .where(BlogAccount.user_id == self.user_id)
            .where(BlogAccount.platform == platform)
        )
        return self.db.scalar(statement)

    def upsert(self, platform: str, username: str) -> BlogAccount:
        existing = self.get_by_platform(platform)
        if existing:
            existing.username = username
            existing.last_synced_at = None
            self.db.commit()
            self.db.refresh(existing)
            return existing
        account = BlogAccount(user_id=self.user_id, platform=platform, username=username)
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def delete(self, account_id: str) -> bool:
        account = self.get_by_id(account_id)
        if not account:
            return False
        self.db.delete(account)
        self.db.commit()
        return True


class BlogArticleRepository:
    """ブログ記事リポジトリ。"""

    def __init__(self, db, user_id: str):
        self.db = db
        self.user_id = user_id

    def list_by_user(self, platform: str | None = None) -> list[BlogArticle]:
        statement = (
            select(BlogArticle)
            .join(BlogArticle.account)
            .where(BlogAccount.user_id == self.user_id)
            .options(
                selectinload(BlogArticle.account),
                selectinload(BlogArticle.tag_rows),
            )
        )
        if platform:
            statement = statement.where(BlogAccount.platform == platform)
        statement = statement.order_by(
            BlogArticle.published_at_value.desc(),
            BlogArticle.created_at.desc(),
        )
        return list(self.db.scalars(statement).all())

    def upsert_many(self, articles: list[dict]) -> int:
        normalized_articles = [self._normalize_article(article) for article in articles]
        if not normalized_articles:
            return 0

        account_ids = {article["account_id"] for article in normalized_articles}
        external_ids = {article["external_id"] for article in normalized_articles}
        existing_statement = (
            select(BlogArticle)
            .join(BlogArticle.account)
            .where(BlogAccount.user_id == self.user_id)
            .where(BlogArticle.account_id.in_(account_ids))
            .where(BlogArticle.external_id.in_(external_ids))
            .options(selectinload(BlogArticle.tag_rows))
        )
        existing_articles = list(self.db.scalars(existing_statement).all())
        existing_map = {
            (article.account_id, article.external_id): article for article in existing_articles
        }

        added = 0
        for article in normalized_articles:
            key = (article["account_id"], article["external_id"])
            existing = existing_map.get(key)
            if existing:
                self._apply_article_payload(existing, article)
                continue

            entity = BlogArticle(account_id=article["account_id"])
            self._apply_article_payload(entity, article)
            self.db.add(entity)
            existing_map[key] = entity
            added += 1

        self.db.commit()
        return added

    def sync_many(self, account_id: str, articles: list[dict]) -> int:
        normalized_articles = [self._normalize_article(article) for article in articles]

        existing_statement = (
            select(BlogArticle)
            .join(BlogArticle.account)
            .where(BlogAccount.user_id == self.user_id)
            .where(BlogArticle.account_id == account_id)
            .options(selectinload(BlogArticle.tag_rows))
        )
        existing_articles = list(self.db.scalars(existing_statement).all())
        existing_map = {article.external_id: article for article in existing_articles}
        incoming_external_ids = {article["external_id"] for article in normalized_articles}

        for external_id, article in existing_map.items():
            if external_id not in incoming_external_ids:
                self.db.delete(article)

        added = 0
        for article in normalized_articles:
            existing = existing_map.get(article["external_id"])
            if existing:
                self._apply_article_payload(existing, article)
                continue

            entity = BlogArticle(account_id=account_id)
            self._apply_article_payload(entity, article)
            self.db.add(entity)
            existing_map[article["external_id"]] = entity
            added += 1

        self.db.commit()
        return added

    def count_by_user(self) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(BlogArticle)
                .join(BlogArticle.account)
                .where(BlogAccount.user_id == self.user_id)
            )
            or 0
        )

    def delete_by_account(self, account_id: str, *, commit: bool = True) -> int:
        articles = list(
            self.db.scalars(
                select(BlogArticle)
                .join(BlogArticle.account)
                .where(BlogAccount.user_id == self.user_id)
                .where(BlogArticle.account_id == account_id)
            ).all()
        )
        count = len(articles)
        for article in articles:
            self.db.delete(article)
        if commit:
            self.db.commit()
        return count

    def _normalize_article(self, article: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(article)
        normalized["external_id"] = normalized.get("external_id") or normalized["url"]
        return normalized

    def _apply_article_payload(self, entity: BlogArticle, payload: dict[str, Any]) -> None:
        entity.external_id = payload["external_id"]
        entity.title = payload["title"]
        entity.url = payload["url"]
        entity.published_at_value = (
            parse_iso_date(payload["published_at"]) if payload.get("published_at") else None
        )
        entity.likes_count = payload.get("likes_count", 0)
        entity.summary = payload.get("summary")
        entity.tag_rows = [
            BlogArticleTag(sort_order=index, name=tag)
            for index, tag in enumerate(payload.get("tags", []))
        ]
