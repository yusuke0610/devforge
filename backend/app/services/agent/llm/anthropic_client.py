"""Anthropic API クライアント（本番用。モデル: Claude Haiku 4.5）。"""

import json
import logging

import anthropic

from ....core import settings
from ..output_schema import TOOL_NAME, build_tool_definition
from .base import LLMClient, LLMError

logger = logging.getLogger(__name__)

# 差分 operations の小さい JSON を返す用途のため Haiku を採用（ADR-0010）。
# 精度不足が判明した場合は claude-sonnet-4-6 へ切り替える。
_MODEL = "claude-haiku-4-5"
# operations JSON（最大 4500 文字のテキスト置換 + 説明文）に十分な上限
_MAX_TOKENS = 4096
_TIMEOUT_SECONDS = 60.0
# 職務経歴書の改善提案は事実忠実性が最優先のため低温度に固定する
_TEMPERATURE = 0.2


class AnthropicClient(LLMClient):
    """Anthropic Messages API を呼び出すクライアント。"""

    def __init__(self) -> None:
        """ANTHROPIC_API_KEY を検証し、非同期クライアントを初期化する。"""
        api_key = settings.get_anthropic_api_key()
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY が設定されていません")
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key, timeout=_TIMEOUT_SECONDS
        )

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        output_schema: dict,
    ) -> str:
        """tool use 強制で Anthropic API を呼び出し、tool input を JSON 文字列で返す。"""
        try:
            response = await self._client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                temperature=_TEMPERATURE,
                system=system_prompt,
                messages=messages,
                # tool use 強制で出力構造をスキーマに従わせる（JSON mode は使わない）。
                # maxLength は API では強制されないため、上限超過は呼び出し側で破棄する
                tools=[build_tool_definition(output_schema)],
                tool_choice={"type": "tool", "name": TOOL_NAME},
            )
        except (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.APIStatusError,
        ) as exc:
            # API キー等の秘密情報を含めないため例外型のみログに残す
            logger.warning("Anthropic API 呼び出しに失敗: %s", type(exc).__name__)
            raise LLMError(f"Anthropic API error: {type(exc).__name__}") from exc

        block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if block is None:
            raise LLMError("Anthropic API が tool_use 応答を返しませんでした")
        # 履歴契約（前回応答を JSON 文字列で持ち回す）を維持するため再シリアライズして返す
        return json.dumps(block.input, ensure_ascii=False)
