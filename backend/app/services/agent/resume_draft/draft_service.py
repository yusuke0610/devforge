"""経歴書ドラフト生成の中核ロジック（骨格構築 → LLM → 検証 → マージ / ADR-0018）。

本モジュールは DB に触れない（DB 読み取りは router → context.py 経由のみ）。
LLM 呼び出しの失敗契約（LLMError / AgentResponseParseError に usage〈観測用〉を載せる・
リトライは 1 回のみ）はチャット（chat_service）と同一。ADR-0023 で課金は撤去。呼び出しの流れ
（call → parse → retry → usage 合算）自体は ``llm/retry.py`` の共通ヘルパーに集約済み。
入出力（骨格 payload / ドラフト出力スキーマ）はモジュール固有のため、パース処理と
パース後のマージ（``_merge_output``）はこのファイルに残す。
"""

import json
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from ....schemas.agent import AgentModelAlias
from .._utils import strip_code_fence
from ..chat_service import AgentResponseParseError, AgentUsage
from ..llm.factory import get_llm_client
from ..llm.retry import generate_with_retry
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


@dataclass(frozen=True)
class ResumeDraftResult:
    """run_resume_draft の戻り値（PDF 生成用 payload + 観測用の使用量）。"""

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
    text = strip_code_fence(raw)
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
    """経歴書ドラフト payload を生成し、観測用の実トークン使用量とともに返す。

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

    output, usage = await generate_with_retry(
        client=client,
        system_prompt=_SYSTEM_PROMPT,
        messages=messages,
        output_schema=output_schema,
        model_id=spec.model_id,
        model=model,
        parse=lambda raw: _parse_draft(raw, set(allowed_names)),
        log_label="ドラフト",
    )
    return ResumeDraftResult(payload=_merge_output(skeleton, selected, output), usage=usage)
