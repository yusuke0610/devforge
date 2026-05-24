"""タスクハンドラの抽象基底クラス。

各タスク種別は ``TaskHandler`` を継承し、以下を実装する:
  - ``get_record(db, payload)``: payload から対応するキャッシュレコードを取得
  - ``run(session_factory, payload)``: タスク本体の実行

レコード状態遷移（``processing`` / ``completed`` / ``dead_letter`` / ``retrying``）は
worker 側で本基底クラスが提供する共通ロジックを通じて行う。

``run`` が ``session_factory`` を受け取るのは、libSQL (Hrana over HTTP) の idle
stream timeout に対する根本対策のため。LLM や外部 API のような長時間処理の前後で
セッションを開閉し、stream を都度更新する。``get_record`` は短命セッション内で
呼ばれる前提で ``Session`` を受け取る。
"""

from abc import ABC, abstractmethod
from typing import Any, Callable

from sqlalchemy.orm import Session

# タスクハンドラに渡すセッションファクトリ。``SessionLocal`` を直接渡す想定で、
# 呼び出すたびに新しいセッションを返す Callable であればよい。
SessionFactory = Callable[[], Session]


class TaskHandler(ABC):
    """非同期タスクの実行とレコード取得を担う抽象基底クラス。"""

    @abstractmethod
    def get_record(self, db: Session, payload: dict) -> Any | None:
        """payload からキャッシュレコードを取得する（status / error_message 等の更新対象）。

        短命セッション内（``with session_factory() as db:`` のブロック内）で
        呼び出される前提。
        """

    @abstractmethod
    async def run(self, session_factory: SessionFactory, payload: dict) -> None:
        """タスク本体を実行する。

        長時間処理（LLM / 外部 API）の前後でセッションを開閉し、libSQL の
        idle stream timeout を避ける。状態遷移は呼び出し側 (worker) が担う。
        """
