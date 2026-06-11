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
from .output_schema import (
    MAX_SUGGESTION_LENGTH,
    MAX_SUGGESTIONS,
    SCOPE_FIELDS,
    build_output_schema,
)

logger = logging.getLogger(__name__)


class AgentTargetNotFoundError(Exception):
    """target のインデックスが resume コンテキストの範囲外。"""


class AgentResponseParseError(Exception):
    """LLM 応答の JSON パースまたはスキーマ検証に失敗。"""

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

# リトライ時に LLM へフィードバックするエラー文の上限（レジュメ本文を含む
# ValidationError でリトライプロンプトが肥大化するのを防ぐ）
_MAX_RETRY_ERROR_LENGTH = 500


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
    try:
        data = json.loads(raw)
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


async def run_agent_chat(request: AgentChatRequest) -> AgentChatResponse:
    """Agent チャットを実行する。

    Raises:
        AgentTargetNotFoundError: target が範囲外。
        AgentResponseParseError: LLM 応答が不正。
        LLMError: LLM 呼び出しの失敗（llm.base 参照）。
    """
    system_prompt = _SCOPE_PROMPTS[request.scope]
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
    output_schema = _SCOPE_SCHEMAS[request.scope]
    raw = await client.generate(system_prompt, messages, output_schema)
    logger.debug("Agent LLM 生応答（パース前）: len=%d", len(raw))
    try:
        return _parse_response(raw, request.scope)
    except AgentResponseParseError as exc:
        # スキーマ違反応答は 1 回だけリトライする。バリデーションエラーの内容を
        # フィードバックして再生成させ、2 回目も失敗したらそのまま raise
        # （router で 502 + AGENT_PARSE_ERROR にマッピングされる既存契約を維持）
        logger.warning("LLM 応答が出力契約に違反したためリトライ: %s", type(exc).__name__)
        retry_messages = [
            *messages,
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    "直前の応答は出力契約に違反しています。"
                    f"違反内容: {str(exc)[:_MAX_RETRY_ERROR_LENGTH]}\n"
                    "契約に従って同じ依頼への応答を再生成してください。"
                ),
            },
        ]
        raw = await client.generate(system_prompt, retry_messages, output_schema)
        logger.debug("Agent LLM リトライ応答（パース前）: len=%d", len(raw))
        return _parse_response(raw, request.scope)
