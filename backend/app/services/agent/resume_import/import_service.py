"""PDF 抽出テキスト → Resume 互換 payload の構造化抽出（ADR-0024 / #527）。

抽出済みテキスト（``text_extract`` の出力）を Claude Haiku に渡し、構造化出力で
Resume 互換の payload に落とす。DB には触れない。LLM 呼び出しの失敗契約
（LLMError / AgentResponseParseError に usage〈観測用〉を載せる・リトライは 1 回のみ）は
チャット（chat_service）・ドラフト（draft_service）と同一（ADR-0010）。

payload は保存契約（schemas/resume.py の strict なバリデーション）ではなく、フォーム
注入用の緩い形（全フィールド任意・欠落は空）で返す。email 等の未抽出フィールドは
フォーム側でユーザが補完する（#524 / DB 非更新）。
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from ....schemas.agent import AgentModelAlias
from ..chat_service import AgentResponseParseError, AgentUsage
from ..llm.base import LLMError
from ..llm.factory import get_llm_client
from ..model_catalog import get_model_spec
from .output_schema import (
    MAX_BUSINESS_DESCRIPTION_LENGTH,
    MAX_CAREER_SUMMARY_LENGTH,
    MAX_COMPANY_LENGTH,
    MAX_DATE_LENGTH,
    MAX_EXPERIENCE_DESCRIPTION_LENGTH,
    MAX_EXPERIENCES,
    MAX_FULL_NAME_LENGTH,
    MAX_SELF_PR_LENGTH,
    build_import_output_schema,
)

logger = logging.getLogger(__name__)

# システムプロンプトの正本は app/prompts/（チャット・ドラフトと同じ分離）。静的に保つ。
_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
_SYSTEM_PROMPT = (_PROMPTS_DIR / "agent_resume_import.md").read_text(encoding="utf-8")

# リトライ時に LLM へフィードバックするエラー文の上限（chat_service と同じ趣旨）
_MAX_RETRY_ERROR_LENGTH = 500


@dataclass(frozen=True)
class ResumeImportResult:
    """run_resume_import の戻り値（フォーム注入用 payload + 観測用の使用量）。"""

    payload: dict
    usage: AgentUsage


class _ImportExperience(BaseModel):
    """抽出された職歴 1 件（フラット / v1）。"""

    company: str = Field(default="", max_length=MAX_COMPANY_LENGTH)
    business_description: str = Field(default="", max_length=MAX_BUSINESS_DESCRIPTION_LENGTH)
    start_date: str = Field(default="", max_length=MAX_DATE_LENGTH)
    end_date: str = Field(default="", max_length=MAX_DATE_LENGTH)
    description: str = Field(default="", max_length=MAX_EXPERIENCE_DESCRIPTION_LENGTH)


class _ImportOutput(BaseModel):
    """LLM 出力全体の検証用モデル（構造の二重防衛）。"""

    full_name: str = Field(default="", max_length=MAX_FULL_NAME_LENGTH)
    career_summary: str = Field(default="", max_length=MAX_CAREER_SUMMARY_LENGTH)
    self_pr: str = Field(default="", max_length=MAX_SELF_PR_LENGTH)
    experiences: list[_ImportExperience] = Field(
        default_factory=list, max_length=MAX_EXPERIENCES
    )


def _parse_import(raw: str) -> _ImportOutput:
    """LLM 応答をパースして検証する（上限超過・構造不正はパース失敗）。"""
    text = raw.strip()
    # Ollama など tool use ではないローカル実装のコードフェンス耐性（chat_service と同じ）
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        data = json.loads(text)
        return _ImportOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("PDF 抽出 LLM 応答のパースに失敗: %s", type(exc).__name__)
        raise AgentResponseParseError(str(exc)) from exc


async def run_resume_import(model: AgentModelAlias, extracted_text: str) -> ResumeImportResult:
    """抽出テキストから Resume 互換 payload を生成し、観測用の使用量とともに返す。

    Raises:
        AgentResponseParseError: LLM 応答が不正（リトライ後も失敗）。
        LLMError: LLM 呼び出しの失敗。
    """
    spec = get_model_spec(model)
    client = get_llm_client(spec.provider)
    output_schema = build_import_output_schema()
    user_prompt = f"# 経歴書 PDF から抽出したテキスト\n{extracted_text}"
    messages: list[dict[str, str]] = [{"role": "user", "content": user_prompt}]

    # 個人情報（抽出テキスト本文）はログに載せない（メタデータのみ）
    logger.debug("PDF 抽出 LLM 入力: model=%s text_len=%d", model, len(extracted_text))

    # リトライしても 1 回目の API 原価は発生するため、使用量は合算で記録する（観測用 / ADR-0023）
    input_tokens = 0
    output_tokens = 0

    def _usage() -> AgentUsage:
        return AgentUsage(model=model, input_tokens=input_tokens, output_tokens=output_tokens)

    async def _generate_and_account(call_messages: list[dict[str, str]], *, label: str):
        nonlocal input_tokens, output_tokens
        call_result = await client.generate(
            _SYSTEM_PROMPT, call_messages, output_schema, spec.model_id
        )
        input_tokens += call_result.input_tokens
        output_tokens += call_result.output_tokens
        logger.debug("PDF 抽出 LLM %s応答（パース前）: len=%d", label, len(call_result.text))
        return call_result

    result = await _generate_and_account(messages, label="生")
    try:
        output = _parse_import(result.text)
        return ResumeImportResult(payload=output.model_dump(), usage=_usage())
    except AgentResponseParseError as exc:
        # 出力契約違反は 1 回だけリトライ（違反内容をフィードバックして再生成 / ADR-0010）
        logger.warning("PDF 抽出 LLM 応答が出力契約に違反したためリトライ: %s", type(exc).__name__)
        retry_messages = [
            *messages,
            {"role": "assistant", "content": result.text},
            {
                "role": "user",
                "content": (
                    "直前の応答は出力契約に違反しています。"
                    f"違反内容: {str(exc)[:_MAX_RETRY_ERROR_LENGTH]}\n"
                    "契約に従って同じ依頼への応答を再生成してください。"
                ),
            },
        ]

    try:
        result = await _generate_and_account(retry_messages, label="リトライ")
    except LLMError as retry_exc:
        retry_exc.usage = _usage()
        raise
    try:
        output = _parse_import(result.text)
    except AgentResponseParseError as retry_exc:
        raise AgentResponseParseError(str(retry_exc), usage=_usage()) from retry_exc
    return ResumeImportResult(payload=output.model_dump(), usage=_usage())
