"""Ollama クライアント（ローカル開発用。REST 直呼び）。"""

import json
import logging

import httpx

from ....core import settings
from .base import LLMClient, LLMError

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 120.0


class OllamaClient(LLMClient):
    """ローカル Ollama の /api/chat を呼び出すクライアント。

    ``format: json`` を指定して JSON のみの応答を強制する
    （ローカルの小型モデルは前置きテキストを混ぜやすいため）。
    """

    def __init__(self) -> None:
        self._base_url = settings.get_ollama_base_url()
        self._model = settings.get_ollama_model()

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat", json=payload
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Ollama API 呼び出しに失敗: %s", type(exc).__name__)
            raise LLMError(f"Ollama API error: {type(exc).__name__}") from exc

        try:
            text = response.json().get("message", {}).get("content", "")
        except json.JSONDecodeError as exc:
            logger.warning("Ollama 応答の JSON パースに失敗: %s", type(exc).__name__)
            raise LLMError("Ollama 応答が JSON ではありません") from exc
        if not text:
            raise LLMError("Ollama から空の応答が返されました")
        return text
