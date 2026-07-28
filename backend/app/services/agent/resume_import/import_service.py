"""PDF 抽出テキスト → Resume 互換 payload の構造化抽出（ADR-0024 / #527）。

抽出済みテキスト（``text_extract`` の出力）を Claude Haiku に渡し、構造化出力で
Resume 互換の payload に落とす。DB には触れない。LLM 呼び出しの失敗契約
（LLMError / AgentResponseParseError に usage〈観測用〉を載せる・リトライは 1 回のみ）は
チャット（chat_service）・ドラフト（draft_service）と同一（ADR-0010）。呼び出しの流れ
（call → parse → retry → usage 合算）自体は ``llm/retry.py`` の共通ヘルパーに集約済み。

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
from .._utils import strip_code_fence
from ..llm.base import AgentResponseParseError, AgentUsage
from ..llm.factory import get_llm_client
from ..llm.retry import generate_with_retry
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
    text = strip_code_fence(raw)
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

    output, usage = await generate_with_retry(
        client=client,
        system_prompt=_SYSTEM_PROMPT,
        messages=messages,
        output_schema=output_schema,
        model_id=spec.model_id,
        model=model,
        parse=_parse_import,
        log_label="PDF 抽出",
    )
    return ResumeImportResult(payload=output.model_dump(), usage=usage)
