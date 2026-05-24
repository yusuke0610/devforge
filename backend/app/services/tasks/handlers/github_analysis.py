"""GitHub 分析タスクのハンドラ。"""

from sqlalchemy.orm import Session

from ....models import GitHubAnalysisCache
from .base import SessionFactory, TaskHandler


class GitHubAnalysisHandler(TaskHandler):
    """GitHub リポジトリ分析タスク。"""

    def get_record(self, db: Session, payload: dict) -> GitHubAnalysisCache | None:
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return db.query(GitHubAnalysisCache).filter_by(user_id=user_id).first()

    async def run(self, session_factory: SessionFactory, payload: dict) -> None:
        # 循環インポート回避のため遅延 import する
        from ...intelligence.github_analysis_service import run_github_analysis

        await run_github_analysis(session_factory, payload)
