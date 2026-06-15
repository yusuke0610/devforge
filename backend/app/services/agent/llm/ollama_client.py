"""Ollama クライアント（ローカル開発用。REST 直呼び）。"""

import json
import logging

import httpx

from ....core import settings
from .base import LLMClient, LLMError, LLMResult

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 120.0


class OllamaClient(LLMClient):
    """ローカル Ollama の /api/chat を呼び出すクライアント。

    ``format`` に JSON Schema を渡して構造化出力（文法制約）を強制する。
    構造・許可 field（const）・maxItems は文法レベルで保証されるが、
    maxLength は強制されないため上限超過は呼び出し側で破棄する。
    """

    def __init__(self) -> None:
        """設定から Ollama のベース URL とモデル名を読み込む。"""
        self._base_url = settings.get_ollama_base_url()
        self._model = settings.get_ollama_model()

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
            data = response.json()
        except json.JSONDecodeError as exc:
            logger.warning("Ollama 応答の JSON パースに失敗: %s", type(exc).__name__)
            raise LLMError("Ollama 応答が JSON ではありません") from exc
        # dict 以外（配列・文字列等）が返ると .get で AttributeError になるため LLMError（502）に倒す
        if not isinstance(data, dict):
            logger.warning("Ollama 応答が想定外の型: %s", type(data).__name__)
            raise LLMError("Ollama 応答が想定外の形式です")
        text = data.get("message", {}).get("content", "")
        if not text:
            raise LLMError("Ollama から空の応答が返されました")
        return LLMResult(text=text)
