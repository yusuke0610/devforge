"""Agent チャットの中核ロジック（コンテキスト組み立て → LLM → operations 検証）。

フロントが編集中フォームをリクエストに載せて送り、レスポンスの operations は
フロントの state にのみ適用される（DB を更新しない原則 / ADR-0010）。
参照データ（GitHub 分析サマリー）は router が context_builder 経由で読み取って渡す。
本モジュールは DB に触れない。
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from ...schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentExperienceContext,
    AgentOperation,
    AgentProjectContext,
    ExperienceTarget,
    ProjectTarget,
)
from ._utils import strip_code_fence
from .llm.base import AgentResponseParseError, AgentUsage
from .llm.factory import get_llm_client
from .llm.retry import generate_with_retry
from .model_catalog import get_model_spec
from .output_schema import (
    MAX_SUGGESTION_LENGTH,
    MAX_SUGGESTIONS,
    SCOPE_FIELDS,
    build_output_schema,
)

logger = logging.getLogger(__name__)

# AgentResponseParseError / AgentUsage は llm/base.py が正本（llm/retry.py との循環 import を
# 避けるため）。本モジュールからも従来どおり import できるよう re-export する。
__all__ = [
    "AgentChatResult",
    "AgentResponseParseError",
    "AgentTargetNotFoundError",
    "AgentUsage",
    "run_agent_chat",
]


class AgentTargetNotFoundError(Exception):
    """target のインデックスが resume コンテキストの範囲外。"""


@dataclass(frozen=True)
class AgentChatResult:
    """run_agent_chat の戻り値（API レスポンス + 観測用の使用量）。"""

    response: AgentChatResponse
    usage: AgentUsage


# 許可外の field 名を返された時の正規化先。スコープ選択で編集対象は確定しているため、
# 小型 LLM が「自己PR」等の field 名を返しても既定 field の提案として救済する。
# project / experience は複数候補だが、自由記述の実体は description なので description に倒す
_SCOPE_DEFAULT_FIELD: dict[str, str] = {
    "career_summary": "career_summary",
    "self_pr": "self_pr",
    "project": "description",
    "experience": "description",
}

# システムプロンプトの正本は app/prompts/ の md ファイル（プロンプト文言の変更を
# コードと分離するため）。共通ルール（agent_base.md）にスコープ固有の品質基準
# （agent_{scope}.md）を結合し、該当スコープの md だけを読ませる（無関係なスコープの
# 指示を混ぜると小型 LLM が文字数制限等を取り違えるため）。
# 許可 field・文字数上限などの機械検証可能な制約はプロンプトに書かず、
# 構造化出力スキーマ（output_schema.py）に持たせる（ADR-0010「制約の責務分離」）
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _load_scope_prompt(scope: str) -> str:
    """base＋スコープ md を結合した system prompt を返す。"""
    base = (_PROMPTS_DIR / "agent_base.md").read_text(encoding="utf-8")
    scope_part = (_PROMPTS_DIR / f"agent_{scope}.md").read_text(encoding="utf-8")
    return f"{base}\n{scope_part}"


_SCOPE_PROMPTS: dict[str, str] = {scope: _load_scope_prompt(scope) for scope in SCOPE_FIELDS}

# 構造化出力スキーマもスコープごとに静的なのでロード時に構築する
_SCOPE_SCHEMAS: dict[str, dict] = {scope: build_output_schema(scope) for scope in SCOPE_FIELDS}


def _build_context(request: AgentChatRequest, reference: dict | None = None) -> str:
    """スコープに応じて LLM に渡すコンテキスト文字列を組み立てる。

    reference には router が context_builder 経由で取得した GitHub 参照データを渡す。
    career_summary / self_pr スコープの場合のみ参照データをコンテキストに含める。
    """
    resume = request.resume
    # 編集対象フィールドのキーは operations の正規 field 名（career_summary 等）に揃える。
    # 小型 LLM はコンテキストのキー名を operations.field に流用しやすいため、
    # 日本語キーにすると許可外 field として破棄される（パース失敗の主因だった）
    if request.scope == "career_summary":
        ctx: dict = {
            "career_summary": resume.career_summary,
            "在籍企業の概要": [
                {"会社": e.company, "事業内容": e.business_description}
                for e in resume.experiences
            ],
        }
        if reference:
            ctx.update(reference)
        return json.dumps(ctx, ensure_ascii=False)
    if request.scope == "self_pr":
        ctx = {
            "self_pr": resume.self_pr,
            "職務要約（参考情報）": resume.career_summary,
        }
        if reference:
            ctx.update(reference)
        return json.dumps(ctx, ensure_ascii=False)
    if request.scope == "experience":
        exp = _resolve_target_experience(request)
        return json.dumps(
            {
                "会社": exp.company,
                "business_description": exp.business_description,
                "description": exp.description,
                "IT企業かどうか": exp.is_it_company,
                "取引先・プロジェクト一覧（参考情報）": [
                    {"取引先": c.name, "プロジェクト数": len(c.projects)}
                    for c in exp.clients
                ],
            },
            ensure_ascii=False,
        )
    project = _resolve_target_project(request)
    return json.dumps(
        {
            "プロジェクト名": project.name,
            "role": project.role,
            "description": project.description,
            "技術スタック": [s.name for s in project.technology_stacks if s.name],
            "担当工程": project.phases,
        },
        ensure_ascii=False,
    )


def _resolve_target_experience(request: AgentChatRequest) -> AgentExperienceContext:
    """target のインデックスから対象在籍企業を取り出す。範囲外は専用例外。"""
    target = request.target
    # scope=experience のとき target は schema で必須検証済み
    assert isinstance(target, ExperienceTarget)
    try:
        return request.resume.experiences[target.experience_index]
    except IndexError as exc:
        raise AgentTargetNotFoundError(
            f"target index out of range: {target}"
        ) from exc


def _resolve_target_project(request: AgentChatRequest) -> AgentProjectContext:
    """target のインデックスから対象プロジェクトを取り出す。範囲外は専用例外。"""
    target = request.target
    # scope=project のとき target は schema で ProjectTarget（client_index/project_index 必須）に検証済み
    assert isinstance(target, ProjectTarget)
    try:
        return (
            request.resume.experiences[target.experience_index]
            .clients[target.client_index]
            .projects[target.project_index]
        )
    except IndexError as exc:
        raise AgentTargetNotFoundError(
            f"target index out of range: {target}"
        ) from exc


def _parse_response(raw: str, scope: str) -> AgentChatResponse:
    """LLM 応答をパースし、field の正規化と上限超過 operation の破棄を行って返す。"""
    text = strip_code_fence(raw)
    try:
        data = json.loads(text)
        parsed = AgentChatResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("LLM 応答のパースに失敗: %s", type(exc).__name__)
        raise AgentResponseParseError(str(exc)) from exc

    allowed = SCOPE_FIELDS[scope]
    operations: list[AgentOperation] = []
    for op in parsed.operations:
        if op.field not in allowed:
            # 許可外の field 名はスコープの既定 field の提案として正規化する
            # （スコープ選択で編集対象は確定しており、提案を捨てるよりユーザー利益が大きい）
            normalized = _SCOPE_DEFAULT_FIELD[scope]
            logger.warning(
                "許可外の field を正規化: scope=%s field=%s -> %s", scope, op.field, normalized
            )
            op = AgentOperation(field=normalized, value=op.value)
        if len(op.value) > allowed[op.field]:
            logger.warning(
                "文字数上限超過の operation を破棄: field=%s len=%d", op.field, len(op.value)
            )
            continue
        operations.append(op)

    # suggestions（次の依頼候補）は operations が空のときだけ意味を持つ。
    # 提案がある応答に混ざって返された場合は UI が混乱するため破棄する
    suggestions: list[str] = []
    if not operations:
        for suggestion in parsed.suggestions:
            text = suggestion.strip()
            if not text or len(text) > MAX_SUGGESTION_LENGTH:
                logger.warning("不正な suggestion を破棄: len=%d", len(text))
                continue
            suggestions.append(text)
        if len(suggestions) > MAX_SUGGESTIONS:
            logger.warning("suggestions が上限超過のため切り詰め: %d 件", len(suggestions))
            suggestions = suggestions[:MAX_SUGGESTIONS]
    return AgentChatResponse(message=parsed.message, operations=operations, suggestions=suggestions)


async def run_agent_chat(
    request: AgentChatRequest, reference: dict | None = None
) -> AgentChatResult:
    """Agent チャットを実行し、レスポンスと実トークン使用量を返す。

    Args:
        reference: GitHub 参照コンテキスト（career_summary / self_pr スコープのみ有効）。
                   router が context_builder 経由で取得して渡す。None の場合は省略される。

    Raises:
        AgentTargetNotFoundError: target が範囲外。
        AgentResponseParseError: LLM 応答が不正。
        LLMError: LLM 呼び出しの失敗（llm.base 参照）。
    """
    system_prompt = _SCOPE_PROMPTS[request.scope]
    # エイリアス → プロバイダ・実モデル ID の解決はサーバー側で行う（クライアントに実 ID を持たせない）
    spec = get_model_spec(request.model)
    model_id = spec.model_id
    user_prompt = (
        f"# 編集対象スコープ\n{request.scope}\n\n"
        f"# 現在の内容\n{_build_context(request, reference)}\n\n"
        f"# ユーザーの依頼\n{request.prompt}"
    )
    # 調査用ログはメタデータのみ出す。レジュメ本文・プロンプト本文は個人情報を含むため
    # DEBUG でもログに載せない（.claude/rules/security.md「ログへの秘密情報出力禁止」）
    logger.debug(
        "Agent LLM 入力: scope=%s model=%s target=%s history=%d resume_len=%d user_prompt_len=%d",
        request.scope,
        request.model,
        request.target,
        len(request.history),
        len(request.resume.model_dump_json()),
        len(user_prompt),
    )
    # 履歴（直近 3 往復）の後ろに今回の user prompt を置く。レジュメコンテキストは
    # 最新ターンにのみ載せる（履歴側はフロントが依頼文 / 前回応答 JSON だけを送る契約）
    messages = [{"role": e.role, "content": e.text} for e in request.history]
    messages.append({"role": "user", "content": user_prompt})
    client = get_llm_client(spec.provider)
    output_schema = _SCOPE_SCHEMAS[request.scope]

    response, usage = await generate_with_retry(
        client=client,
        system_prompt=system_prompt,
        messages=messages,
        output_schema=output_schema,
        model_id=model_id,
        model=request.model,
        parse=lambda raw: _parse_response(raw, request.scope),
        log_label="Agent",
    )
    return AgentChatResult(response=response, usage=usage)
