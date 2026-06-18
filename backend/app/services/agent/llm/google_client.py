"""Google Generative AI（Gemini）クライアント（ADR-0013）。

モデルは model_catalog.py で解決した実 ID（gemini-2.5-flash / gemini-2.5-pro）を使う。
構造化出力は ``response_mime_type=application/json`` + ``response_schema``（controlled
generation）で強制する。Anthropic の tool use とは機構が異なるが、応答テキストは同じく
スキーマに従う JSON のシリアライズ文字列として返す。
"""

import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from ....core import settings
from ..output_schema import to_portable_schema
from .base import LLMClient, LLMError, LLMResult

logger = logging.getLogger(__name__)

# 職務経歴書の改善提案は事実忠実性が最優先のため低温度に固定する
_TEMPERATURE = 0.2
_TIMEOUT_SECONDS = 60.0


class GoogleClient(LLMClient):
    """Gemini API（google-genai SDK）を呼び出すクライアント。"""

    def __init__(self) -> None:
        """GOOGLE_API_KEY を検証し、非同期クライアントを初期化する。"""
        api_key = settings.get_google_api_key()
        if not api_key:
            raise LLMError("GOOGLE_API_KEY が設定されていません")
        self._client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(timeout=int(_TIMEOUT_SECONDS * 1000)),
        )

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        output_schema: dict,
        model_id: str,
    ) -> LLMResult:
        """response_schema で構造化出力を強制し、応答 JSON と実使用量を返す。"""
        # Gemini の役割名は user / model。assistant → model に読み替える
        contents = [
            genai_types.Content(
                role="model" if m["role"] == "assistant" else "user",
                parts=[genai_types.Part.from_text(text=m["content"])],
            )
            for m in messages
        ]
        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=_TEMPERATURE,
            response_mime_type="application/json",
            response_schema=to_portable_schema(output_schema),
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=model_id, contents=contents, config=config
            )
        except genai_errors.APIError as exc:
            # API キー等の秘密情報を含めないため例外型のみログに残す
            logger.warning("Google API 呼び出しに失敗: %s", type(exc).__name__)
            raise LLMError(f"Google API error: {type(exc).__name__}") from exc

        text = response.text
        if not text:
            raise LLMError("Google API が空の応答を返しました")
        # usage はクレジット課金（ADR-0012）の根拠となるため実測値をそのまま返す
        usage = response.usage_metadata
        return LLMResult(
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )
