"""経歴書ドラフト生成キャッシュ（``ResumeDraftCache``）のデータアクセス。

``ResumeDraftCache`` はユーザーあたり 1 件のレコードで、``user_id`` を一意境界とする。
取得・作成クエリを本リポジトリへ集約し、router / handler / task_runner からの直クエリ散在を防ぐ。
``user_id`` スコープは IDOR 防止の認可境界であり、1 箇所に閉じ込めることで条件追加時の漏れを防ぐ
（``GitHubLinkCacheRepository`` と同形）。
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import ResumeDraftCache


class ResumeDraftCacheRepository:
    """ユーザーの経歴書ドラフト生成キャッシュの読み取り・作成。

    セッションはコンストラクタで受け取る。ドラフト生成の実行経路では libSQL の
    idle stream timeout 対策でフェーズごとにセッションを開閉するため、本リポジトリは
    セッションを保持せず呼び出し側が渡したものをそのまま使う。
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_user(self, user_id: str) -> ResumeDraftCache | None:
        """ユーザーのキャッシュを取得する。存在しなければ ``None``。"""
        return self.db.scalar(
            select(ResumeDraftCache).where(ResumeDraftCache.user_id == user_id)
        )

    def get_or_create(self, user_id: str) -> ResumeDraftCache:
        """ユーザーのキャッシュを取得し、存在しなければ作成して flush する。

        並列リクエストが ``user_id`` の一意制約で衝突した場合は rollback して再取得する。
        再 SELECT が ``None`` を返したら ``RuntimeError`` を上げて non-Optional な戻り値契約を守る
        （.claude/rules/backend/database.md「IntegrityError 後の再 SELECT は None を判定する」）。
        """
        cache = self.get_by_user(user_id)
        if cache is not None:
            return cache

        cache = ResumeDraftCache(user_id=user_id)
        self.db.add(cache)
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_user(user_id)
            if existing is None:
                raise RuntimeError(
                    f"ResumeDraftCache の作成と再取得に失敗しました (user_id={user_id})"
                ) from None
            return existing
        return cache
