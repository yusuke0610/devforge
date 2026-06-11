"""Agent チャットの中核ロジック（コンテキスト組み立て → LLM → operations 検証）。

DB アクセスは行わない。フロントが編集中フォームをリクエストに載せて送り、
レスポンスの operations はフロントの state にのみ適用される（DB を更新しない原則 / ADR-0010）。
"""

import json
import logging
from pathlib import Path

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

# 許可外の field 名を返された時の正規化先。スコープ選択で編集対象は確定しているため、
# 小型 LLM が「自己PR」等の field 名を返しても既定 field の提案として救済する。
# project は role / description の 2 候補だが、自由記述の実体は description のみ
# （role は 1 行の肩書き入力）なので description に倒す
_SCOPE_DEFAULT_FIELD: dict[str, str] = {
    "career_summary": "career_summary",
    "self_pr": "self_pr",
    "project": "description",
}

# システムプロンプトの正本は app/prompts/ の md ファイル（プロンプト文言の変更を
# コードと分離するため）。{allowed_fields} / {field_limits} はプレースホルダ。
# JSON 例の {} を .format で二重括弧にエスケープせず済むよう、埋め込みは str.replace で行う
_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "agent_chat_system.md"
_SYSTEM_PROMPT = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _build_context(request: AgentChatRequest) -> str:
    """スコープに応じて LLM に渡すコンテキスト文字列を組み立てる。"""
    resume = request.resume
    # 編集対象フィールドのキーは operations の正規 field 名（career_summary 等）に揃える。
    # 小型 LLM はコンテキストのキー名を operations.field に流用しやすいため、
    # 日本語キーにすると許可外 field として破棄される（パース失敗の主因だった）
    if request.scope == "career_summary":
        return json.dumps(
            {
                "career_summary": resume.career_summary,
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
                "self_pr": resume.self_pr,
                "職務要約（参考情報）": resume.career_summary,
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
    """LLM 応答をパースし、field の正規化と上限超過 operation の破棄を行って返す。"""
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
    return AgentChatResponse(message=parsed.message, operations=operations)


async def run_agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    """Agent チャットを実行する。

    Raises:
        AgentTargetNotFoundError: target が範囲外。
        AgentResponseParseError: LLM 応答が不正。
        LLMError: LLM 呼び出しの失敗（llm.base 参照）。
    """
    allowed = _SCOPE_FIELDS[request.scope]
    system_prompt = _SYSTEM_PROMPT.replace(
        "{allowed_fields}", ", ".join(allowed)
    ).replace(
        "{field_limits}", ", ".join(f"{k}: {v}文字" for k, v in allowed.items())
    )
    user_prompt = (
        f"# 編集対象スコープ\n{request.scope}\n\n"
        f"# 現在の内容\n{_build_context(request)}\n\n"
        f"# ユーザーの依頼\n{request.prompt}"
    )
    # 調査用ログはメタデータのみ出す。レジュメ本文・プロンプト本文は個人情報を含むため
    # DEBUG でもログに載せない（.claude/rules/security.md「ログへの秘密情報出力禁止」）
    logger.debug(
        "Agent LLM 入力: scope=%s target=%s history=%d resume_len=%d user_prompt_len=%d",
        request.scope,
        request.target,
        len(request.history),
        len(request.resume.model_dump_json()),
        len(user_prompt),
    )
    # 履歴（直近 3 往復）の後ろに今回の user prompt を置く。レジュメコンテキストは
    # 最新ターンにのみ載せる（履歴側はフロントが依頼文 / 前回応答 JSON だけを送る契約）
    messages = [{"role": e.role, "content": e.text} for e in request.history]
    messages.append({"role": "user", "content": user_prompt})
    client = get_llm_client()
    raw = await client.generate(system_prompt, messages)
    logger.debug("Agent LLM 生応答（パース前）: len=%d", len(raw))
    return _parse_response(raw, request.scope)
