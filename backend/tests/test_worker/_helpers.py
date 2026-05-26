"""tests/test_worker パッケージ内で共有するヘルパ。"""

import asyncio

from sqlalchemy.orm import Session


def run_sync(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def keep_open_session(db: Session):
    """worker が finally で呼ぶ ``db.close()`` を no-op 化するプロキシを返す。

    worker は終端処理ごとに ``SessionLocal()`` を開いて finally で close するが、
    テストでは同じ ``db_session`` を検証側でも使い続けたいため close を握りつぶす。
    close 時は ``expire_all()`` のみ行い、次回 refresh で最新の DB 状態を読めるようにする。
    """

    class _Proxy:
        def __init__(self, real: Session) -> None:
            self._real = real

        def __getattr__(self, name):
            return getattr(self._real, name)

        def close(self) -> None:
            self._real.expire_all()

    return _Proxy(db)
