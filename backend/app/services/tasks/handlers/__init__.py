"""バックグラウンドタスクのハンドラレジストリ。

各タスク種別ごとに ``TaskHandler`` を実装し、ここで登録する。
worker は本レジストリを介してタスクを実行する。
"""

from typing import Dict

from ..base import TaskType
from .base import TaskHandler
from .github_analysis import GitHubAnalysisHandler

_HANDLERS: Dict[TaskType, TaskHandler] = {
    TaskType.GITHUB_ANALYSIS: GitHubAnalysisHandler(),
}


def get_handler(task_type: TaskType) -> TaskHandler | None:
    """タスク種別からハンドラを取得する。未登録の場合は ``None`` を返す。"""
    return _HANDLERS.get(task_type)


__all__ = [
    "TaskHandler",
    "get_handler",
]
