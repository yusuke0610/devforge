"""ブログアカウント同期サービス。

外部 API からの記事取得・正規化・DB保存のロジックを router から分離する。
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...repositories import BlogAccountRepository, BlogArticleRepository
from ...schemas import BlogSyncResponse
from .collector import (
    BlogAccountNotFoundError,
    BlogPlatformRequestError,
    UnsupportedBlogPlatformError,
    fetch_articles,
    normalize_username,
    verify_user_exists,
)

logger = logging.getLogger(__name__)


class BlogSyncService:
    """ブログアカウントの同期処理を担うサービスクラス。"""

    def __init__(self, db: Session, user_id: str) -> None:
        self._db = db
        self._user_id = user_id
        self._account_repo = BlogAccountRepository(db, user_id)
        self._article_repo = BlogArticleRepository(db, user_id)

    def get_account_or_none(self, account_id: str):
        """指定 ID のアカウントを返す。存在しない場合は None。"""
        return self._account_repo.get_by_id(account_id)

    async def sync(self, account_id: str) -> BlogSyncResponse:
        """外部 API からデータを取得して DB に保存し、同期結果を返す。

        Raises:
            UnsupportedBlogPlatformError: サポート外のプラットフォームの場合。
            BlogPlatformRequestError: 外部 API リクエストに失敗した場合。
        """
        account = self._account_repo.get_by_id(account_id)
        if not account:
            raise ValueError(f"アカウントが見つかりません: {account_id}")

        try:
            normalized_username = normalize_username(account.platform, account.username)
            user_exists = await verify_user_exists(account.platform, normalized_username)
            if not user_exists:
                raise BlogAccountNotFoundError(
                    f"アカウントが見つかりません: {account.platform}/{account.username}"
                )
            raw_articles = await fetch_articles(account.platform, normalized_username)
        except BlogAccountNotFoundError:
            raise
        except UnsupportedBlogPlatformError:
            raise
        except ValueError as exc:
            raise BlogAccountNotFoundError(
                f"アカウントが見つかりません: {account.platform}/{account.username}"
            ) from exc
        except Exception:
            logger.exception(
                "ブログ記事の取得に失敗しました: %s/%s",
                account.platform,
                account.username,
            )
            raise BlogPlatformRequestError(
                f"記事取得に失敗しました: {account.platform}/{account.username}"
            )

        for art in raw_articles:
            art["account_id"] = account.id

        if normalized_username != account.username:
            account.username = normalized_username

        account.last_synced_at = datetime.now(timezone.utc)

        synced = self._article_repo.sync_many(account.id, raw_articles)
        total = self._article_repo.count_by_user()

        return BlogSyncResponse(synced_count=synced, total_count=total)
