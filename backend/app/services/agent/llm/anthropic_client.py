"""Anthropic API クライアント（本番用。モデル: Claude Haiku 4.5）。"""

import logging

import anthropic

from ....core import settings
from .base import LLMClient, LLMError

logger = logging.getLogger(__name__)

# 差分 operations の小さい JSON を返す用途のため Haiku を採用（ADR-0010）。
# 精度不足が判明した場合は claude-sonnet-4-6 へ切り替える。
_MODEL = "claude-haiku-4-5"
# operations JSON（最大 4500 文字のテキスト置換 + 説明文）に十分な上限
_MAX_TOKENS = 4096
_TIMEOUT_SECONDS = 60.0


class AnthropicClient(LLMClient):
    """Anthropic Messages API を呼び出すクライアント。"""

    def __init__(self) -> None:
        api_key = settings.get_anthropic_api_key()
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY が設定されていません")
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, timeout=_TIMEOUT_SECONDS
        )

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = await self._client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.APIStatusError,
        ) as exc:
            # API キー等の秘密情報を含めないため例外型のみログに残す
            logger.warning("Anthropic API 呼び出しに失敗: %s", type(exc).__name__)
            raise LLMError(f"Anthropic API error: {type(exc).__name__}") from exc

        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        if not text:
            raise LLMError("Anthropic API から空の応答が返されました")
        return text
