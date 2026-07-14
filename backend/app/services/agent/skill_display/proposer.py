"""スキル表示名の提案ロジック（実在スキル → LLM → 提案グループ / ADR-0016 D11）。

agent は表示名・畳み込みグループを **提案するだけ**で、確定・永続化はしない（D8 / P4）。
本モジュールは DB に触れない（DB 読み取りは router → repository 経由）。LLM 呼び出しの
失敗契約（LLMError / AgentResponseParseError に usage を載せ課金漏れを防ぐ・リトライ 1 回）は
チャット / ドラフトと同一。入出力（スキル一覧 / グループ提案）が異なるため共通化しない
（Rule of Three / .claude/rules/common/duplication.md）。
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
from .output_schema import MAX_DISPLAY_NAME_LENGTH, build_skill_display_output_schema

logger = logging.getLogger(__name__)

# システムプロンプトの正本は app/prompts/（チャット / ドラフトと同じ分離）。動的情報
# （スキル一覧・許可 token）は user メッセージの JSON とスキーマの enum に載せ、md は静的に保つ
_PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
_SYSTEM_PROMPT = (_PROMPTS_DIR / "agent_skill_display.md").read_text(encoding="utf-8")

# リトライ時に LLM へフィードバックするエラー文の上限（chat_service / draft_service と同じ趣旨）
_MAX_RETRY_ERROR_LENGTH = 500

# 1 回の提案で LLM に渡すスキルの上限（送信トークン・構造化出力 enum サイズを抑える）。
# 大量スキル（実測 180 件超）を 1 ショットで投げると入力が肥大し、モデルが巨大 enum の
# 構造化 JSON を壊しやすい。evidence の多い順で切り、ロングテールは提案対象外とする
# （呼び出し側で language 除外・並べ替えをしてから渡す想定）。
MAX_SKILLS_PER_PROPOSAL = 50


@dataclass(frozen=True)
class SkillIdentity:
    """提案対象・確定のキーになるスキルの安定 identity（github_skills と一致）。"""

    kind: str
    ecosystem: str
    canonical_name: str


@dataclass(frozen=True)
class SkillForProposal:
    """提案に渡す 1 スキル（identity + 機械が持つ表示ヒント）。"""

    kind: str
    ecosystem: str
    canonical_name: str
    # 機械（Linguist）由来の表示補正。無ければ None（package/infra は基本 None）
    machine_display_name: str | None = None
    parent: str | None = None

    @property
    def identity(self) -> SkillIdentity:
        return SkillIdentity(self.kind, self.ecosystem, self.canonical_name)


@dataclass(frozen=True)
class ProposedGroup:
    """LLM が提案した 1 表示スキル（表示名 + 畳むメンバー群）。"""

    display_name: str
    members: list[SkillIdentity]


@dataclass(frozen=True)
class SkillDisplayProposalResult:
    """propose_skill_display_names の戻り値（提案 + 課金用の使用量）。"""

    groups: list[ProposedGroup]
    usage: AgentUsage


class _Group(BaseModel):
    """LLM 出力の 1 グループ（構造の二重防衛）。"""

    display_name: str = Field(min_length=1)
    members: list[str] = Field(default_factory=list)


class _ProposalOutput(BaseModel):
    """LLM 出力全体の検証用モデル。"""

    groups: list[_Group] = Field(default_factory=list)


def _token(skill: SkillForProposal) -> str:
    """スキル identity を LLM が参照する一意 token に符号化する。

    ``(kind, ecosystem, canonical_name)`` は一意なので、ecosystem（無ければ kind）を
    接頭辞にした ``prefix:canonical`` で衝突しない読みやすい token になる。
    """
    prefix = skill.ecosystem or skill.kind
    return f"{prefix}:{skill.canonical_name}"


def _build_context(tokened_skills: list[tuple[str, SkillForProposal]]) -> str:
    """LLM に渡すスキル一覧の JSON コンテキストを組み立てる。

    各スキルの token・種別・現在の表示（機械補正 or canonical）を渡す。捏造判定の根拠に
    なる「与えた情報」の全量であり、members はこの token 集合からしか選べない。
    """
    entries = [
        {
            "token": token,
            "kind": skill.kind,
            "ecosystem": skill.ecosystem or None,
            "name": skill.canonical_name,
            "current": skill.machine_display_name or skill.canonical_name,
        }
        for token, skill in tokened_skills
    ]
    return json.dumps({"skills": entries}, ensure_ascii=False)


def _parse_proposal(
    raw: str, identity_by_token: dict[str, SkillIdentity]
) -> list[ProposedGroup]:
    """LLM 応答をパースし、許可外 token・重複メンバー・空グループを破棄して返す。

    - members の token は許可集合（identity_by_token）に無ければ破棄（捏造排除の二重防衛）。
    - 1 スキルは 1 グループにのみ属する（既に別グループへ割当済みの token は破棄）。
    - display_name の空・上限超過は当該グループを破棄（切り詰めない / ADR-0010 踏襲）。
    - メンバーが 1 件も残らないグループは破棄。
    """
    text = raw.strip()
    # Ollama 等 tool use ではないローカル実装のコードフェンス耐性（chat_service と同じ）
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        data = json.loads(text)
        parsed = _ProposalOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("表示名提案 LLM 応答のパースに失敗: %s", type(exc).__name__)
        raise AgentResponseParseError(str(exc)) from exc

    groups: list[ProposedGroup] = []
    assigned: set[str] = set()
    for group in parsed.groups:
        name = group.display_name.strip()
        if not name or len(name) > MAX_DISPLAY_NAME_LENGTH:
            logger.warning("不正な表示名のグループを破棄: len=%d", len(name))
            continue
        members: list[SkillIdentity] = []
        for token in group.members:
            identity = identity_by_token.get(token)
            if identity is None:
                logger.warning("許可外の member token を破棄: %s", token)
                continue
            if token in assigned:
                logger.warning("重複割当の member token を破棄: %s", token)
                continue
            assigned.add(token)
            members.append(identity)
        if not members:
            logger.warning("メンバーが残らないグループを破棄: %s", name)
            continue
        groups.append(ProposedGroup(display_name=name, members=members))
    return groups


async def propose_skill_display_names(
    model: AgentModelAlias, skills: list[SkillForProposal]
) -> SkillDisplayProposalResult:
    """スキル一覧から表示名・畳み込みグループの提案を生成し、使用量とともに返す。

    Args:
        model: モデルエイリアス（router のスキーマで検証済み）。
        skills: 提案対象スキル（MAX_SKILLS_PER_PROPOSAL 件まで。超過分は呼び出し側で切る）。

    Raises:
        AgentResponseParseError: LLM 応答が不正（リトライ後も失敗）。
        LLMError: LLM 呼び出しの失敗。
    """
    # token ↔ identity の対応を作る。token は _token で一意（衝突しない / 上記 docstring）
    tokened_skills: list[tuple[str, SkillForProposal]] = [(_token(s), s) for s in skills]
    identity_by_token: dict[str, SkillIdentity] = {
        token: skill.identity for token, skill in tokened_skills
    }

    spec = get_model_spec(model)
    client = get_llm_client(spec.provider)
    output_schema = build_skill_display_output_schema(list(identity_by_token.keys()))
    user_prompt = f"# スキル一覧\n{_build_context(tokened_skills)}"
    messages: list[dict[str, str]] = [{"role": "user", "content": user_prompt}]

    logger.debug(
        "表示名提案 LLM 入力: model=%s skills=%d prompt_len=%d",
        model,
        len(skills),
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
        logger.debug("表示名提案 LLM %s応答（パース前）: len=%d", label, len(call_result.text))
        return call_result

    result = await _generate_and_account(messages, label="生")
    try:
        groups = _parse_proposal(result.text, identity_by_token)
        return SkillDisplayProposalResult(groups=groups, usage=_usage())
    except AgentResponseParseError as exc:
        # 出力契約違反は 1 回だけリトライ（違反内容をフィードバックして再生成 / ADR-0010）
        logger.warning("表示名提案 LLM 応答が出力契約に違反したためリトライ: %s", type(exc).__name__)
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
        groups = _parse_proposal(result.text, identity_by_token)
    except AgentResponseParseError as retry_exc:
        # 2 回目も失敗。合算使用量を載せて伝播する（課金漏れ防止 / ADR-0012）
        raise AgentResponseParseError(str(retry_exc), usage=_usage()) from retry_exc
    return SkillDisplayProposalResult(groups=groups, usage=_usage())
