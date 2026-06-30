"""通知リポジトリ。"""

from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from ..models.notification import Notification


class NotificationRepository:
    """ユーザー通知のデータアクセス層。"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def list_recent(self, limit: int = 30) -> list[Notification]:
        """最新の通知を取得する。"""
        stmt = (
            select(Notification)
            .where(Notification.user_id == self.user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def unread_count(self) -> int:
        """未読件数を返す。"""
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == self.user_id, Notification.is_read.is_(False))
        )
        return self.db.scalar(stmt) or 0

    def mark_read(self, notification_id: str) -> bool:
        """指定 ID の通知を既読にする。対象が存在しない場合は False を返す。"""
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == self.user_id)
            .values(is_read=True)
        )
        result = cast("CursorResult[Any]", self.db.execute(stmt))
        self.db.commit()
        return result.rowcount > 0

    def mark_all_read(self) -> int:
        """全通知を既読にし、更新件数を返す。"""
        stmt = (
            update(Notification)
            .where(Notification.user_id == self.user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        result = cast("CursorResult[Any]", self.db.execute(stmt))
        self.db.commit()
        return result.rowcount

    @staticmethod
    def create(db: Session, user_id: str, task_type: str, status: str, title: str, message: str | None = None) -> Notification:
        """通知を作成する。DB セッションを引数で受け取り、任意のコンテキストから呼び出せる。"""
        notification = Notification(
            user_id=user_id,
            task_type=task_type,
            status=status,
            title=title,
            message=message,
        )
        db.add(notification)
        db.commit()
        return notification
