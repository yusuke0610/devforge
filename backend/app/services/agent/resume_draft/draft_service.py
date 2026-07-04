"""経歴書ドラフト生成の中核ロジック（骨格構築 → LLM → 検証 → マージ / ADR-0018）。

本モジュールは DB に触れない（DB 読み取りは router → context.py 経由のみ）。
LLM 呼び出しの失敗契約（LLMError / AgentResponseParseError に usage を載せて課金漏れを
防ぐ・リトライは 1 回のみ）はチャット（chat_service）と同一。呼び出しの流れも同じ形だが、
入出力（骨格 payload / ドラフト出力スキーマ）が異なるため現時点では共通化しない
（Rule of Three / .claude/rules/common/duplication.md）。
"""

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from ....schemas.agent import AgentModelAlias
from ..chat_service import AgentResponseParseError, AgentUsage
from ..llm.base import LLMError
from ..llm.factory import get_llm_client
from ..model_catalog import get_model_spec
from .context import DraftSource
from .mapper import build_skeleton, select_repos
from .output_schema import (
    MAX_CAREER_SUMMARY_LENGTH,
    MAX_PROJECT_DESCRIPTION_LENGTH,
    MAX_SELF_PR_LENGTH,
    build_draft_output_schema,
)

logger = logging.getLogger(__name__)

# システムプロンプトの正本は app/prompts/（チャットと同じ分離）。動的プレースホルダは
# 使わず静的に保つ（プロバイダキャッシュを効かせる）。動的情報（リポ情報・許可集合）は
# user メッセージの JSON とスキーマの enum に載せる
_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
_SYSTEM_PROMPT = (_PROMPTS_DIR / "agent_resume_draft.md").read_text(encoding="utf-8")

# リトライ時に LLM へフィードバックするエラー文の上限（chat_service と同じ趣旨）
_MAX_RETRY_ERROR_LENGTH = 500


@dataclass(frozen=True)
class ResumeDraftResult:
    """run_resume_draft の戻り値（PDF 生成用 payload + 課金用の使用量）。"""

    payload: dict
    usage: AgentUsage


class _ProjectDescription(BaseModel):
    """LLM 出力のプロジェクト説明 1 件分。"""

    repo_full_name: str
    description: str


class _DraftOutput(BaseModel):
    """LLM 出力全体の検証用モデル（構造の二重防衛）。"""

    career_summary: str = Field(min_length=1, max_length=MAX_CAREER_SUMMARY_LENGTH)
    self_pr: str = Field(min_length=1, max_length=MAX_SELF_PR_LENGTH)
    project_descriptions: list[_ProjectDescription] = Field(default_factory=list)


def _build_repo_context(source: DraftSource, selected: list) -> str:
    """LLM に渡すリポジトリ情報の JSON コンテキストを組み立てる。

    捏造禁止の判定根拠になる「与えた情報」の全量。技術名は骨格に載せる集合と同じ
    ものを渡す（スタック上限で絞る前の反転結果ではなく、mapper の選定結果に依存
    させないよう名前だけを列挙する）。
    """
    repos = [
        {
            "repo_full_name": repo.full_name,
            "description": repo.description,
            "created_at": repo.created_at,
            "pushed_at": repo.pushed_at,
            "technologies": sorted(
                {tech.name for tech in source.repo_technologies.get(repo.full_name, [])}
            ),
        }
        for repo in selected
    ]
    return json.dumps({"github_username": source.username, "repos": repos}, ensure_ascii=False)


def _parse_draft(raw: str, allowed_names: set[str]) -> _DraftOutput:
    """LLM 応答をパースし、リポジトリ名の検証と重複・許可外の破棄を行って返す。

    career_summary / self_pr の欠落・上限超過は契約違反としてパース失敗にする
    （切り詰めない / ADR-0010 踏襲）。プロジェクト説明のみ個別に degrade する
    （許可外・重複・上限超過の 1 件を破棄しても、骨格側の repo description
    フォールバックで経歴書として成立するため）。
    """
    text = raw.strip()
    # Ollama など tool use ではないローカル実装のコードフェンス耐性（chat_service と同じ）
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        data = json.loads(text)
        parsed = _DraftOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("ドラフト LLM 応答のパースに失敗: %s", type(exc).__name__)
        raise AgentResponseParseError(str(exc)) from exc

    descriptions: list[_ProjectDescription] = []
    seen: set[str] = set()
    for item in parsed.project_descriptions:
        if item.repo_full_name not in allowed_names:
            logger.warning("許可外リポジトリの説明を破棄: %s", item.repo_full_name)
            continue
        if item.repo_full_name in seen:
            logger.warning("重複したリポジトリ説明を破棄: %s", item.repo_full_name)
            continue
        if len(item.description) > MAX_PROJECT_DESCRIPTION_LENGTH:
            logger.warning(
                "文字数上限超過のプロジェクト説明を破棄: repo=%s len=%d",
                item.repo_full_name,
                len(item.description),
            )
            continue
        seen.add(item.repo_full_name)
        descriptions.append(item)
    return _DraftOutput(
        career_summary=parsed.career_summary,
        self_pr=parsed.self_pr,
        project_descriptions=descriptions,
    )


def _merge_output(skeleton: dict, selected: list, output: _DraftOutput) -> dict:
    """骨格 payload に LLM の自然文をマージする。

    説明が返らなかったプロジェクトは骨格の repo description フォールバックのまま残す。
    """
    skeleton["career_summary"] = output.career_summary
    skeleton["self_pr"] = output.self_pr

    by_name = {item.repo_full_name: item.description for item in output.project_descriptions}
    projects = skeleton["experiences"][0]["clients"][0]["projects"]
    for repo, project in zip(selected, projects):
        description = by_name.get(repo.full_name)
        if description is None:
            logger.warning("プロジェクト説明が欠落（フォールバック使用）: %s", repo.full_name)
            continue
        project["description"] = description
    return skeleton


async def run_resume_draft(
    model: AgentModelAlias, source: DraftSource, *, today: date | None = None
) -> ResumeDraftResult:
    """経歴書ドラフト payload を生成し、課金用の実トークン使用量とともに返す。

    Args:
        model: モデルエイリアス（AgentModelAlias。router のスキーマで検証済み）。
        source: context.build_draft_source が組み立てた連携データ。
        today: 「参画中」判定の基準日（テスト注入用。省略時は当日）。

    Raises:
        AgentResponseParseError: LLM 応答が不正（リトライ後も失敗）。
        LLMError: LLM 呼び出しの失敗。
    """
    selected = select_repos(source)
    skeleton = build_skeleton(source, selected, today=today)
    allowed_names = [repo.full_name for repo in selected]

    spec = get_model_spec(model)
    client = get_llm_client(spec.provider)
    output_schema = build_draft_output_schema(allowed_names)
    user_prompt = f"# リポジトリ情報\n{_build_repo_context(source, selected)}"
    messages: list[dict[str, str]] = [{"role": "user", "content": user_prompt}]

    # 個人情報・リポジトリ本文はログに載せない（メタデータのみ）
    logger.debug(
        "ドラフト LLM 入力: model=%s repos=%d prompt_len=%d",
        model,
        len(selected),
        len(user_prompt),
    )

    # リトライしても 1 回目の API 原価は発生しているため、使用量は合算で課金する（ADR-0012）
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
        logger.debug("ドラフト LLM %s応答（パース前）: len=%d", label, len(call_result.text))
        return call_result

    result = await _generate_and_account(messages, label="生")
    try:
        output = _parse_draft(result.text, set(allowed_names))
        return ResumeDraftResult(
            payload=_merge_output(skeleton, selected, output), usage=_usage()
        )
    except AgentResponseParseError as exc:
        # 出力契約違反は 1 回だけリトライ（違反内容をフィードバックして再生成 / ADR-0010）
        logger.warning("ドラフト LLM 応答が出力契約に違反したためリトライ: %s", type(exc).__name__)
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
        # 1 回目の API 原価は発生済み。使用量を載せて router 側で課金を確定させる（ADR-0012）
        retry_exc.usage = _usage()
        raise
    try:
        output = _parse_draft(result.text, set(allowed_names))
    except AgentResponseParseError as retry_exc:
        # 2 回目も失敗。合算使用量を載せて伝播する（課金漏れ防止 / ADR-0012）
        raise AgentResponseParseError(str(retry_exc), usage=_usage()) from retry_exc
    return ResumeDraftResult(payload=_merge_output(skeleton, selected, output), usage=_usage())
