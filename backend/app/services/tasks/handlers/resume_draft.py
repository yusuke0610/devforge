"""経歴書ドラフト生成タスクのハンドラ（ADR-0018 / 非同期化）。"""

from sqlalchemy.orm import Session

from ....models import ResumeDraftCache
from ....repositories.resume_draft import ResumeDraftCacheRepository
from .base import SessionFactory, TaskHandler


class ResumeDraftHandler(TaskHandler):
    """経歴書ドラフト生成タスク。連携データ → LLM → PDF レンダリング検証 → 保存。"""

    def get_record(self, db: Session, payload: dict) -> ResumeDraftCache | None:
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return ResumeDraftCacheRepository(db).get_by_user(user_id)

    async def run(self, session_factory: SessionFactory, payload: dict) -> None:
        # 循環インポート回避のため遅延 import する
        from ...agent.resume_draft.run_task import run_resume_draft_task

        await run_resume_draft_task(session_factory, payload)
