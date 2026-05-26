"""非同期タスクのキャッシュレコード操作とディスパッチを共通化するサービス。

3つの非同期タスク（GitHub 連携 / ブログサマリ / キャリア分析）はいずれも
``status`` / ``error_message`` / ``retry_count`` / ``started_at`` / ``completed_at``
を持つキャッシュレコードに紐づき、以下のフローを取る:

  1. 進行中タスクの有無を確認
  2. キャッシュを ``pending`` にリセット（再実行時は ``retry_count`` も 0 へ）
  3. ディスパッチ
  4. ディスパッチ失敗時に ``dead_letter`` へ遷移

この共通フローを ``AsyncTaskCacheService`` に集約することで、ルーター層から
キャッシュ状態管理の重複コードを排除する。
"""

import logging
from typing import Protocol

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from .base import TaskType, is_in_progress, is_retryable_terminal
from .factory import get_task_dispatcher


class _AsyncTaskRecord(Protocol):
    """status / error_message / retry_count などを持つキャッシュレコードの構造的型。

    GitHubLinkCache が満たす。
    """

    status: str
    error_message: str | None
    retry_count: int
    started_at: object
    completed_at: object


class AsyncTaskCacheService:
    """非同期タスクのキャッシュレコードに対する状態遷移とディスパッチを担う。

    ルーター層は本サービスを介してのみキャッシュレコードの ``status`` を更新する。
    （worker 側の状態遷移は ``services/tasks/worker.py`` が担う）
    """

    def __init__(self, db: Session, record: _AsyncTaskRecord) -> None:
        self._db = db
        self._record = record

    @property
    def status(self) -> str:
        return self._record.status

    def is_in_progress(self) -> bool:
        """``pending`` / ``processing`` の進行中状態かどうかを返す。"""
        return is_in_progress(self._record.status)

    def is_retryable_terminal(self) -> bool:
        """``dead_letter`` 等、手動再実行可能な終端状態かどうかを返す。"""
        return is_retryable_terminal(self._record.status)

    def reset_to_pending(self, *, reset_retry_count: bool = False) -> None:
        """キャッシュを ``pending`` 状態にリセットする。

        ``reset_retry_count=True`` を指定するとリトライカウントもリセットする
        （手動再実行時に使用）。
        """
        self._record.status = "pending"
        self._record.error_message = None
        if reset_retry_count:
            self._record.retry_count = 0
            self._record.started_at = None
            self._record.completed_at = None
        self._db.commit()

    def try_reset_to_pending(self, *, reset_retry_count: bool = False) -> bool:
        """DB から最新状態を取得してから ``pending`` へアトミックに遷移する。

        既に ``pending`` / ``processing`` であれば何もせず False を返す。
        遷移に成功した場合は True を返す。
        ``reset_to_pending`` の代わりにこちらを使うことで TOCTOU を軽減できる。
        """
        self._db.refresh(self._record)
        if is_in_progress(self._record.status):
            return False
        self.reset_to_pending(reset_retry_count=reset_retry_count)
        return True

    async def dispatch(
        self,
        background_tasks: BackgroundTasks,
        task_type: TaskType,
        payload: dict,
        *,
        failure_message: str,
        logger: logging.Logger,
    ) -> None:
        """タスクをディスパッチし、失敗時はキャッシュを ``dead_letter`` に遷移させる。

        例外は呼び出し側でハンドリングするため再 raise する。
        ルーター層は本メソッドが投げた例外を捕捉して HTTP 5xx に変換すること。
        """
        try:
            dispatcher = get_task_dispatcher(background_tasks)
            await dispatcher.dispatch(task_type, payload)
        except Exception:
            logger.exception("%s タスクのディスパッチに失敗しました", task_type.value)
            self._record.status = "dead_letter"
            self._record.error_message = failure_message
            self._db.commit()
            raise
