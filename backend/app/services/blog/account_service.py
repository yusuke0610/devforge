"""ブログ連携アカウントの更新サービス。"""

from sqlalchemy.orm import Session

from ...models import BlogAccount
from ...repositories import BlogAccountRepository, BlogArticleRepository
from .collector import (
    BlogAccountNotFoundError,
    BlogPlatformRequestError,
    UnsupportedBlogPlatformError,
    normalize_username,
    verify_user_exists,
)


class BlogAccountService:
    """ブログ連携アカウントの更新処理を扱う。"""

    def __init__(self, db: Session, user_id: str) -> None:
        self._db = db
        self._user_id = user_id
        self._account_repo = BlogAccountRepository(db, user_id)
        self._article_repo = BlogArticleRepository(db, user_id)

    def get_by_platform(self, platform: str) -> BlogAccount | None:
        return self._account_repo.get_by_platform(platform)

    async def update_username(self, platform: str, username: str) -> BlogAccount:
        account = self._account_repo.get_by_platform(platform)
        if not account:
            raise ValueError(f"アカウントが見つかりません: {platform}")

        normalized_username = normalize_username(platform, username)

        try:
            user_exists = await verify_user_exists(platform, normalized_username)
        except (UnsupportedBlogPlatformError, BlogPlatformRequestError):
            raise

        if not user_exists:
            raise BlogAccountNotFoundError(f"アカウントが見つかりません: {platform}/{username}")

        try:
            self._article_repo.delete_by_account(account.id, commit=False)
            account.username = normalized_username
            account.last_synced_at = None
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise

        self._db.refresh(account)
        return account
