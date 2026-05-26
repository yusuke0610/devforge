"""tests/test_worker パッケージ内で共有するヘルパ。"""

import asyncio

from sqlalchemy.orm import Session


def run_sync(coro):
    """
    Run a coroutine to completion on a new event loop and return its result.
    
    Parameters:
        coro: A coroutine or awaitable to execute.
    
    Returns:
        The value produced by the coroutine.
    
    Notes:
        The function creates a fresh event loop and always closes it after completion or if an exception occurs.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def keep_open_session(db: Session):
    """
    Provide a Session proxy whose close() does not close the underlying session.
    
    Used in tests to prevent worker code from closing a shared Session: attribute access is delegated to the original Session, and calling close() calls `expire_all()` on the real session instead of closing it so the test can continue to use the same Session.
    
    Parameters:
        db (Session): The real SQLAlchemy Session to wrap.
    
    Returns:
        A proxy object exposing the same attributes as `db`; its `close()` method calls `db.expire_all()` rather than closing `db`.
    """

    class _Proxy:
        def __init__(self, real: Session) -> None:
            """
            Initialize the proxy with the underlying SQLAlchemy Session.
            
            Parameters:
                real (Session): The actual Session instance to which attribute access and operations are delegated.
            """
            self._real = real

        def __getattr__(self, name):
            """
            Delegate attribute access to the underlying real Session.
            
            Parameters:
                name (str): Attribute name being accessed on the proxy.
            
            Returns:
                The attribute or method with the given name from the proxied `self._real`.
            """
            return getattr(self._real, name)

        def close(self) -> None:
            """
            Mark all ORM objects in the proxied Session as expired without closing the underlying Session.
            
            Invokes `expire_all()` on the wrapped `Session` to expire loaded instances while keeping the session open for reuse by callers.
            """
            self._real.expire_all()

    return _Proxy(db)
