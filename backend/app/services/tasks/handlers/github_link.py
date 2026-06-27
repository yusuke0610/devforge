"""GitHub 連携タスクのハンドラ。"""

from sqlalchemy.orm import Session

from ....models import GitHubLinkCache
from ....repositories.github_link import GitHubLinkCacheRepository
from .base import SessionFactory, TaskHandler


class GitHubLinkHandler(TaskHandler):
    """GitHub リポジトリ連携タスク。"""

    def get_record(self, db: Session, payload: dict) -> GitHubLinkCache | None:
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return GitHubLinkCacheRepository(db).get_by_user(user_id)

    async def run(self, session_factory: SessionFactory, payload: dict) -> None:
        # 循環インポート回避のため遅延 import する
        from ...intelligence.github_link_service import run_github_link

        await run_github_link(session_factory, payload)
