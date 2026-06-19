"""Ollama クライアント（ローカル開発用。REST 直呼び）。"""

import json
import logging
import time

import httpx

from ....core import settings
from .base import LLMClient, LLMError, LLMResult, require_text, wrap_api_error

logger = logging.getLogger(__name__)

# この秒数を超えた呼び出しは警告ログを出し、タイムアウト値の妥当性を判断する材料にする
_SLOW_REQUEST_THRESHOLD_SECONDS = 120.0


class OllamaClient(LLMClient):
    """ローカル Ollama の /api/chat を呼び出すクライアント。

    ``format`` に JSON Schema を渡して構造化出力（文法制約）を強制する。
    構造・許可 field（const）・maxItems は文法レベルで保証されるが、
    maxLength は強制されないため上限超過は呼び出し側で破棄する。
    """

    def __init__(self) -> None:
        """設定から Ollama のベース URL・モデル名・タイムアウトを読み込む。"""
        self._base_url = settings.get_ollama_base_url()
        self._model = settings.get_ollama_model()
        self._timeout_seconds = settings.get_ollama_timeout_seconds()

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        output_schema: dict,
        model_id: str,
    ) -> LLMResult:
        """Ollama /api/chat に JSON Schema 形式の format を付与して呼び出し、応答テキストを返す。

        model_id（Anthropic 用の実モデル ID）は使わず、ローカル設定（OLLAMA_MODEL）の
        モデルを使う。トークン使用量は返せないため 0 とする（ローカルは無料扱い / ADR-0012）。
        """
        payload = {
            "model": self._model,
            "messages": [{"role": "system", "content": system_prompt}, *messages],
            "stream": False,
            "format": output_schema,
            # 職務経歴書の改善提案は事実忠実性が最優先のため低温度に固定する
            # （デフォルト 0.8 では小型モデルが架空の資格・技術を捏造しやすい）
            "options": {"temperature": 0.2},
        }
        started_at = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat", json=payload
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise wrap_api_error("Ollama", exc) from exc

        elapsed = time.monotonic() - started_at
        if elapsed >= _SLOW_REQUEST_THRESHOLD_SECONDS:
            # 閾値超過が常態化するならタイムアウト値（OLLAMA_TIMEOUT_SECONDS）の見直し材料にする
            logger.warning(
                "Ollama 応答が遅延: %.1fs（閾値 %.0fs / タイムアウト %.0fs）",
                elapsed,
                _SLOW_REQUEST_THRESHOLD_SECONDS,
                self._timeout_seconds,
            )

        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            logger.warning("Ollama 応答の JSON パースに失敗: %s", type(exc).__name__)
            raise LLMError("Ollama 応答が JSON ではありません") from exc
        # dict 以外（配列・文字列等）が返ると .get で AttributeError になるため LLMError（502）に倒す
        if not isinstance(data, dict):
            logger.warning("Ollama 応答が想定外の型: %s", type(data).__name__)
            raise LLMError("Ollama 応答が想定外の形式です")
        # message が dict でない（エラー応答で文字列/null 等）場合も .get で
        # AttributeError になるため、トップレベルと同様に LLMError（502）へ倒す
        message = data.get("message")
        if not isinstance(message, dict):
            logger.warning("Ollama 応答の message が想定外の型: %s", type(message).__name__)
            raise LLMError("Ollama 応答が想定外の形式です")
        content = message.get("content")
        if not isinstance(content, str):
            logger.warning("Ollama 応答の content が想定外の型: %s", type(content).__name__)
            raise LLMError("Ollama 応答が想定外の形式です")
        text = require_text("Ollama", content)
        return LLMResult(text=text)
