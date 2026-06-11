"""Agent チャットの中核ロジック（コンテキスト組み立て → LLM → operations 検証）。

DB アクセスは行わない。フロントが編集中フォームをリクエストに載せて送り、
レスポンスの operations はフロントの state にのみ適用される（DB を更新しない原則 / ADR-0010）。
"""

import json
import logging

from pydantic import ValidationError

from ...schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentOperation,
    AgentProjectContext,
)
from .llm.factory import get_llm_client

logger = logging.getLogger(__name__)


class AgentTargetNotFoundError(Exception):
    """target のインデックスが resume コンテキストの範囲外。"""


class AgentResponseParseError(Exception):
    """LLM 応答の JSON パースまたはスキーマ検証に失敗。"""


# スコープごとに operations が編集してよいフィールドと文字数上限
_SCOPE_FIELDS: dict[str, dict[str, int]] = {
    "career_summary": {"career_summary": 2000},
    "self_pr": {"self_pr": 2000},
    "project": {"description": 4500, "role": 200},
}

_SYSTEM_PROMPT = """\
あなたは日本語の職務経歴書の改善を支援するアシスタントです。
ユーザーの依頼に基づき、編集対象フィールドの改善案を JSON で返してください。

# 出力形式（JSON のみ。前置き・コードフェンス・補足テキストは一切禁止）
{{"message": "<提案の説明（日本語）>", "operations": [{{"field": "<フィールド名>", "value": "<新しい本文>"}}]}}

# ルール
- operations の field は次のみ許可: {allowed_fields}
- 各フィールドの文字数上限: {field_limits}
- 提案が不要・不可能な場合は operations を空配列にし、message で理由を説明する
- value は職務経歴書にそのまま掲載できる完成した日本語の文章にする
"""


def _build_context(request: AgentChatRequest) -> str:
    """スコープに応じて LLM に渡すコンテキスト文字列を組み立てる。"""
    resume = request.resume
    if request.scope == "career_summary":
        return json.dumps(
            {
                "現在の職務要約": resume.career_summary,
                "在籍企業の概要": [
                    {"会社": e.company, "事業内容": e.business_description}
                    for e in resume.experiences
                ],
            },
            ensure_ascii=False,
        )
    if request.scope == "self_pr":
        return json.dumps(
            {
                "現在の自己PR": resume.self_pr,
                "職務要約": resume.career_summary,
            },
            ensure_ascii=False,
        )
    project = _resolve_target_project(request)
    return json.dumps(
        {
            "プロジェクト名": project.name,
            "現在の役割": project.role,
            "現在の詳細": project.description,
            "技術スタック": [s.name for s in project.technology_stacks if s.name],
            "担当工程": project.phases,
        },
        ensure_ascii=False,
    )


def _resolve_target_project(request: AgentChatRequest) -> AgentProjectContext:
    """target のインデックスから対象プロジェクトを取り出す。範囲外は専用例外。"""
    target = request.target
    # scope=project のとき target は schema で必須検証済み
    assert target is not None
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
    """LLM 応答をパースし、スコープ外・上限超過の operation を破棄して返す。"""
    text = raw.strip()
    # JSON のみを指示しても小型モデルはコードフェンスを付けることがあるため除去する
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        data = json.loads(text)
        parsed = AgentChatResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("LLM 応答のパースに失敗: %s", type(exc).__name__)
        raise AgentResponseParseError(str(exc)) from exc

    allowed = _SCOPE_FIELDS[scope]
    operations: list[AgentOperation] = []
    for op in parsed.operations:
        if op.field not in allowed:
            # スコープ外フィールドの提案は適用先が特定できないため破棄する
            logger.warning("スコープ外の operation を破棄: scope=%s field=%s", scope, op.field)
            continue
        if len(op.value) > allowed[op.field]:
            logger.warning(
                "文字数上限超過の operation を破棄: field=%s len=%d", op.field, len(op.value)
            )
            continue
        operations.append(op)
    return AgentChatResponse(message=parsed.message, operations=operations)


async def run_agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    """Agent チャットを実行する。

    Raises:
        AgentTargetNotFoundError: target が範囲外。
        AgentResponseParseError: LLM 応答が不正。
        LLMError: LLM 呼び出しの失敗（llm.base 参照）。
    """
    allowed = _SCOPE_FIELDS[request.scope]
    system_prompt = _SYSTEM_PROMPT.format(
        allowed_fields=", ".join(allowed),
        field_limits=", ".join(f"{k}: {v}文字" for k, v in allowed.items()),
    )
    user_prompt = (
        f"# 編集対象スコープ\n{request.scope}\n\n"
        f"# 現在の内容\n{_build_context(request)}\n\n"
        f"# ユーザーの依頼\n{request.prompt}"
    )
    client = get_llm_client()
    raw = await client.generate(system_prompt, user_prompt)
    return _parse_response(raw, request.scope)
