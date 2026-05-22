"""LLM を使った職務経歴書判定と構造化抽出。"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from ..intelligence.llm.base import LLMClient
from ..tasks.exceptions import NonRetryableError, RetryableError

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
# 判定に使うテキストの最大文字数（冒頭部分のみ渡す）
_JUDGE_TEXT_MAX_CHARS = 3000
# LLM 判定で is_resume=True かつ confidence がこれ以上のときのみ次のステップへ進む
_CONFIDENCE_THRESHOLD = 0.6


@dataclass
class JudgeResult:
    is_resume: bool
    confidence: float
    reason: str


def _load_prompt(filename: str) -> str:
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"プロンプトファイルが見つかりません: {path}")
    return path.read_text(encoding="utf-8").strip()


def _strip_code_block(text: str) -> str:
    """LLM がコードブロックで包んで返した場合に除去する。"""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    return text


async def judge_is_resume(text: str, llm_client: LLMClient) -> JudgeResult:
    """テキストが職務経歴書かどうかを LLM で判定する。

    confidence が _CONFIDENCE_THRESHOLD 未満または is_resume=False の場合は
    is_resume=False を返す。LLM 呼び出し失敗は RetryableError / NonRetryableError を再 raise する。
    """
    system_prompt = _load_prompt("judge_resume.md")
    user_prompt = text[:_JUDGE_TEXT_MAX_CHARS]

    raw = await llm_client.generate(system_prompt, user_prompt)
    if raw is None:
        raise RetryableError("LLM 判定に失敗しました（応答なし）")

    try:
        data = json.loads(_strip_code_block(raw))
        is_resume = bool(data.get("is_resume", False))
        confidence = float(data.get("confidence", 0.0))
        reason = str(data.get("reason", ""))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("LLM 判定レスポンスのパースに失敗しました: %s", raw[:200])
        raise NonRetryableError(f"LLM 判定レスポンスのパースに失敗しました: {exc}") from exc

    if confidence < _CONFIDENCE_THRESHOLD:
        is_resume = False
        reason = f"確信度が低いため非職務経歴書と判定しました（confidence={confidence:.2f}）"

    logger.info(
        "職務経歴書判定完了",
        extra={"is_resume": is_resume, "confidence": confidence, "reason": reason},
    )
    return JudgeResult(is_resume=is_resume, confidence=confidence, reason=reason)


async def extract_structured(text: str, llm_client: LLMClient) -> dict:
    """職務経歴書テキストを CareerResumePayload 互換の dict に構造化する。

    LLM 呼び出し失敗や JSON パース失敗は NonRetryableError を raise する。
    """
    system_prompt = _load_prompt("extract_resume.md")

    raw = await llm_client.generate(system_prompt, text)
    if raw is None:
        raise RetryableError("LLM 抽出に失敗しました（応答なし）")

    try:
        data = json.loads(_strip_code_block(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("LLM 抽出レスポンスのパースに失敗しました: %s", raw[:200])
        raise NonRetryableError(f"LLM 抽出レスポンスのパースに失敗しました: {exc}") from exc

    # 必須フィールドの存在確認
    for key in ("full_name", "career_summary", "self_pr", "experiences", "qualifications"):
        if key not in data:
            data[key] = [] if key in ("experiences", "qualifications") else ""

    logger.info("職務経歴書構造化抽出完了", extra={"field_count": len(data)})
    return data
