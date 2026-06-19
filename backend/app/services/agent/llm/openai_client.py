"""OpenAI（GPT）クライアント（ADR-0013）。

モデルは model_catalog.py で解決した実 ID（gpt-4o-mini / gpt-4.1）を使う。
構造化出力は Structured Outputs（``response_format`` の json_schema・strict）で強制する。
応答テキストは Anthropic / Gemini と同じくスキーマに従う JSON のシリアライズ文字列で返す。
"""

import openai

from ....core import settings
from ..output_schema import TOOL_NAME, to_portable_schema
from .base import LLMClient, LLMResult, require_api_key, require_text, wrap_api_error

# 職務経歴書の改善提案は事実忠実性が最優先のため低温度に固定する
_TEMPERATURE = 0.2
_TIMEOUT_SECONDS = 60.0


class OpenAIClient(LLMClient):
    """OpenAI Chat Completions API を呼び出すクライアント。"""

    def __init__(self) -> None:
        """OPENAI_API_KEY を検証し、非同期クライアントを初期化する。"""
        api_key = require_api_key(settings.get_openai_api_key(), "OPENAI_API_KEY")
        self._client = openai.AsyncOpenAI(api_key=api_key, timeout=_TIMEOUT_SECONDS)

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        output_schema: dict,
        model_id: str,
    ) -> LLMResult:
        """Structured Outputs（strict）で構造化出力を強制し、応答 JSON と実使用量を返す。"""
        full_messages = [{"role": "system", "content": system_prompt}, *messages]
        try:
            response = await self._client.chat.completions.create(
                model=model_id,
                temperature=_TEMPERATURE,
                messages=full_messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": TOOL_NAME,
                        "strict": True,
                        "schema": to_portable_schema(output_schema),
                    },
                },
            )
        except openai.OpenAIError as exc:
            raise wrap_api_error("OpenAI", exc) from exc

        raw_text = response.choices[0].message.content if response.choices else None
        text = require_text("OpenAI", raw_text)
        # usage はクレジット課金（ADR-0012）の根拠となるため実測値をそのまま返す
        usage = response.usage
        return LLMResult(
            text=text,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )
