"""Anthropic API クライアント（本番用。モデルは model_catalog.py で解決）。

認証は Vertex AI Model Garden（Cloud Run の SA → ADC）経由で、API キーは使わない
（ADR-0015）。Messages API のロジック（tool use 強制 / usage 抽出）は Vertex
クライアントでも共通のため `generate()` は据え置く。
"""

import json
from typing import Any, cast

import anthropic
from anthropic import AsyncAnthropicVertex  # pyright: ignore[reportPrivateImportUsage]

from ....core import settings
from ..output_schema import TOOL_NAME, build_tool_definition
from .base import LLMClient, LLMError, LLMResult, require_gcp_project, wrap_api_error

# operations JSON（最大 4500 文字のテキスト置換 + 説明文）に十分な上限
_MAX_TOKENS = 4096
_TIMEOUT_SECONDS = 60.0
# 職務経歴書の改善提案は事実忠実性が最優先のため低温度に固定する
_TEMPERATURE = 0.2


class AnthropicClient(LLMClient):
    """Anthropic Messages API を呼び出すクライアント。"""

    def __init__(self) -> None:
        """GCP プロジェクトを検証し、Vertex AI 経由の非同期クライアントを初期化する。"""
        project = require_gcp_project(settings.get_gcp_project_id())
        self._client = AsyncAnthropicVertex(
            project_id=project,
            region=settings.get_vertex_anthropic_location(),
            timeout=_TIMEOUT_SECONDS,
        )

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        output_schema: dict,
        model_id: str,
    ) -> LLMResult:
        """tool use 強制で Anthropic API を呼び出し、tool input と実使用量を返す。"""
        try:
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=_MAX_TOKENS,
                temperature=_TEMPERATURE,
                system=system_prompt,
                # 履歴契約の dict 形は SDK の MessageParam と互換だが静的には別型のため境界で cast。
                messages=cast(Any, messages),
                # tool use 強制で出力構造をスキーマに従わせる（JSON mode は使わない）。
                # maxLength は API では強制されないため、上限超過は呼び出し側で破棄する
                tools=[cast(Any, build_tool_definition(output_schema))],
                tool_choice={"type": "tool", "name": TOOL_NAME},
            )
        except (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.APIStatusError,
        ) as exc:
            raise wrap_api_error("Anthropic", exc) from exc

        block = next(
            (b for b in response.content if b.type == "tool_use"), None
        )
        if block is None:
            raise LLMError("Anthropic API が tool_use 応答を返しませんでした")
        # 履歴契約（前回応答を JSON 文字列で持ち回す）を維持するため再シリアライズして返す。
        # usage はクレジット課金（ADR-0012）の根拠となるため実測値をそのまま返す
        return LLMResult(
            text=json.dumps(block.input, ensure_ascii=False),
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
