"""パフォーマンス計測ユーティリティ。

3 種類の計測手段を提供する:
  - ``measure_time``       : 同期関数デコレータ
  - ``measure_time_async`` : 非同期関数デコレータ
  - ``measure_block``      : 非同期コンテキストマネージャ

出力ログ例 (JSON フォーマット時):
  {"severity": "INFO", "message": "performance", "operation": "github_collector.fetch",
   "duration_ms": 3241, "status": "success", "request_id": "550e8400-..."}

エラー時は status="error", error_type="TimeoutError" を付与して re-raise する。
"""

import functools
import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

_logger = logging.getLogger("devforge.metrics")

F = TypeVar("F", bound=Callable[..., Any])


def measure_time(operation: str) -> Callable[[F], F]:
    """同期関数の実行時間を計測するデコレータ。

    使用例::

        @measure_time("github_collector.fetch")
        def fetch_repositories(...): ...
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                _log_success(operation, start)
                return result
            except Exception as exc:
                _log_error(operation, start, exc)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def measure_time_async(operation: str) -> Callable[[F], F]:
    """非同期関数の実行時間を計測するデコレータ。

    使用例::

        @measure_time_async("github_collector.fetch")
        async def fetch_repositories(...): ...
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                result = await fn(*args, **kwargs)
                _log_success(operation, start)
                return result
            except Exception as exc:
                _log_error(operation, start, exc)
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


@asynccontextmanager
async def measure_block(operation: str) -> AsyncIterator[None]:
    """任意の非同期ブロックの実行時間を計測するコンテキストマネージャ。

    使用例::

        async with measure_block("pipeline.stage.skill_extraction"):
            ...
    """
    start = time.monotonic()
    try:
        yield
        _log_success(operation, start)
    except Exception as exc:
        _log_error(operation, start, exc)
        raise


def _log_success(operation: str, start: float) -> None:
    duration_ms = int((time.monotonic() - start) * 1000)
    _logger.debug(
        "performance",
        extra={"operation": operation, "duration_ms": duration_ms, "status": "success"},
    )


def _log_error(operation: str, start: float, exc: Exception) -> None:
    duration_ms = int((time.monotonic() - start) * 1000)
    _logger.debug(
        "performance",
        extra={
            "operation": operation,
            "duration_ms": duration_ms,
            "status": "error",
            "error_type": type(exc).__name__,
        },
    )
