"""Ollama バックエンドクライアント。"""

import logging
import os
import time

import httpx

from ....core import env_keys
from ....services.tasks.exceptions import NonRetryableError, RetryableError
from .base import LLMClient

logger = logging.getLogger(__name__)

# 一時障害とみなす HTTP ステータスコード
_RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class OllamaClient(LLMClient):
    """Ollama API を使用した LLM クライアント。"""

    def __init__(self) -> None:
        self.base_url = os.environ.get(env_keys.OLLAMA_BASE_URL, "http://localhost:11434")
        self.model = os.environ.get(env_keys.OLLAMA_MODEL, "gemma3:4b")
        self.timeout = float(os.environ.get(env_keys.OLLAMA_TIMEOUT, "1200.0"))  # デフォルトは 20 分

    async def generate(self, system_prompt: str, user_prompt: str) -> str | None:
        """Ollama API でテキスト生成を実行する。

        タイムアウト・5xx・429 は ``RetryableError``、4xx は ``NonRetryableError``
        を raise する。``ConnectError``（Ollama 未起動時）および未分類エラーは ``None`` を返す。
        """
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "system": system_prompt,
                        "prompt": user_prompt,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                duration_ms = int((time.monotonic() - start) * 1000)
                logger.info(
                    "Ollama 生成完了",
                    extra={"status": "completed", "duration_ms": duration_ms},
                )
                return data.get("response", "").strip()
        except httpx.ConnectError:
            logger.info("Ollama が %s で利用できません", self.base_url)
            return None
        except httpx.TimeoutException as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.warning(
                "Ollama 生成がタイムアウトしました (%.1f秒)",
                self.timeout,
                extra={
                    "status": "failed",
                    "error_type": "TimeoutException",
                    "duration_ms": duration_ms,
                },
            )
            raise RetryableError(f"Ollama タイムアウト: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            status_code = exc.response.status_code
            logger.warning(
                "Ollama が %d を返しました", status_code,
                extra={"status": "failed", "duration_ms": duration_ms},
            )
            if status_code in _RETRYABLE_STATUS_CODES:
                retry_after = _parse_retry_after(exc.response) if status_code == 429 else None
                raise RetryableError(
                    f"Ollama {status_code}: {exc}", retry_after=retry_after,
                ) from exc
            raise NonRetryableError(f"Ollama {status_code}: {exc}") from exc
        except Exception:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.exception(
                "Ollama による生成に失敗しました",
                extra={"status": "failed", "duration_ms": duration_ms},
            )
            return None

    async def check_available(self) -> bool:
        """Ollama サーバーに接続可能、かつ指定モデルが利用可能か確認する。"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                models = [m.get("name", "") for m in resp.json().get("models", [])]
                return self.model in models
        except (httpx.ConnectError, httpx.TimeoutException):
            return False


def _parse_retry_after(response: httpx.Response) -> float | None:
    """HTTP レスポンスから ``Retry-After`` ヘッダを秒単位で抽出する。"""
    value = response.headers.get("retry-after")
    if not value:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
