"""タスクディスパッチャーの基底クラス。"""

from abc import ABC, abstractmethod
from enum import Enum


class TaskType(str, Enum):
    """バックグラウンドで実行可能なタスクの種別。"""

    GITHUB_ANALYSIS = "github_analysis"
    BLOG_SUMMARIZE = "blog_summarize"
    CAREER_ANALYSIS = "career_analysis"


# 手動再実行を許可するキャッシュレコードのステータス集合。
# `dead_letter`: リトライ枯渇またはリトライ不可エラーで停止した最終状態。
RETRYABLE_TERMINAL_STATUSES: frozenset[str] = frozenset({"dead_letter"})


# 進行中（pending / processing）とみなすキャッシュレコードのステータス集合。
IN_PROGRESS_STATUSES: frozenset[str] = frozenset({"pending", "processing"})


def is_retryable_terminal(status: str | None) -> bool:
    """status が手動再実行可能な終端状態かどうかを返す。"""
    return status in RETRYABLE_TERMINAL_STATUSES


def is_in_progress(status: str | None) -> bool:
    """status が進行中（pending / processing）かどうかを返す。"""
    return status in IN_PROGRESS_STATUSES


class TaskDispatcher(ABC):
    """タスクをバックグラウンドにディスパッチする共通インターフェース。"""

    @abstractmethod
    async def dispatch(self, task_type: TaskType, payload: dict) -> None:
        """タスクをディスパッチする。payload には user_id と task 固有パラメータを含む。"""
