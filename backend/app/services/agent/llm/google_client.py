"""Google Generative AI（Gemini）クライアント（ADR-0013 / Vertex 化は ADR-0015）。

モデルは model_catalog.py で解決した実 ID（gemini-2.5-flash / gemini-2.5-pro）を使う。
認証は Vertex AI（Cloud Run の SA → ADC）経由で、API キーは使わない（ADR-0015）。
構造化出力は ``response_mime_type=application/json`` + ``response_schema``（controlled
generation）で強制する。Anthropic の tool use とは機構が異なるが、応答テキストは同じく
スキーマに従う JSON のシリアライズ文字列として返す。
"""

from typing import Any, cast

from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from ....core import settings
from ..output_schema import to_portable_schema
from .base import LLMClient, LLMResult, require_gcp_project, require_text, wrap_api_error

# 職務経歴書の改善提案は事実忠実性が最優先のため低温度に固定する
_TEMPERATURE = 0.2
_TIMEOUT_SECONDS = 60.0


class GoogleClient(LLMClient):
    """Gemini API（google-genai SDK）を呼び出すクライアント。"""

    def __init__(self) -> None:
        """GCP プロジェクトを検証し、Vertex AI 経由の非同期クライアントを初期化する。"""
        project = require_gcp_project(settings.get_gcp_project_id())
        self._client = genai.Client(
            vertexai=True,
            project=project,
            location=settings.get_vertex_location(),
            # HttpOptions.timeout はミリ秒単位（google-genai 仕様）。60s = 60000ms
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
            # Gemini の response_schema は additionalProperties 非対応のため除去する
            response_schema=to_portable_schema(output_schema, drop_additional_properties=True),
        )
        try:
            response = await self._client.aio.models.generate_content(
                # list[Content] は ContentListUnion に含まれるが静的には別型のため境界で cast。
                model=model_id, contents=cast(Any, contents), config=config
            )
        except genai_errors.APIError as exc:
            raise wrap_api_error("Google", exc) from exc

        text = require_text("Google", response.text)
        # usage はクレジット課金（ADR-0012）の根拠となるため実測値をそのまま返す
        usage = response.usage_metadata
        return LLMResult(
            text=text,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )
