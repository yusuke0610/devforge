"""LLM 呼び出し → パース → （失敗時）1 回リトライ → usage 合算、の共通オーケストレーション。

chat_service / resume_draft / resume_import / skill_display の 4 モジュールで
一言一句同じだった「1 回目呼び出し → パース → 出力契約違反時に同一文言のフィードバックで
リトライメッセージを組み立て → 2 回目呼び出し → パース」という制御フローを集約する。
リトライ回数（1 回のみ）・``LLMError`` / ``AgentResponseParseError`` への ``usage``
（観測用）付与は `.claude/rules/backend/agent.md` の不変条件であり、ここで一元的に守る
（ADR-0010）。

入出力（プロンプト構築・パース関数・パース後の後処理）はモジュールごとに異なるため、
``parse`` をコールバックとして受け取る高階関数として設計する。
"""

import logging
from collections.abc import Callable
from typing import TypeVar

from ....schemas.agent import AgentModelAlias
from .base import AgentResponseParseError, AgentUsage, LLMClient, LLMError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# リトライ時に LLM へフィードバックするエラー文の上限（レジュメ本文等を含む
# ValidationError でリトライプロンプトが肥大化するのを防ぐ）。4 モジュール共通の値。
_MAX_RETRY_ERROR_LENGTH = 500


def _build_retry_feedback(error: Exception) -> dict[str, str]:
    """出力契約違反のフィードバックメッセージ（user ロール）を組み立てる。

    4 モジュールで一言一句同じ文言（.claude/rules/backend/agent.md「エラー契約」）。
    """
    return {
        "role": "user",
        "content": (
            "直前の応答は出力契約に違反しています。"
            f"違反内容: {str(error)[:_MAX_RETRY_ERROR_LENGTH]}\n"
            "契約に従って同じ依頼への応答を再生成してください。"
        ),
    }


async def generate_with_retry(
    *,
    client: LLMClient,
    system_prompt: str,
    messages: list[dict[str, str]],
    output_schema: dict,
    model_id: str,
    model: AgentModelAlias,
    parse: Callable[[str], T],
    log_label: str,
) -> tuple[T, AgentUsage]:
    """LLM を呼び出し、``parse`` でパースする。失敗時は 1 回だけリトライする。

    Args:
        client: 呼び出し済みの LLM クライアント（``get_llm_client`` で解決済み）。
        system_prompt: system プロンプト（呼び出し元で静的にロード済みのものを渡す）。
        messages: 1 回目呼び出しに渡す会話（今回の user プロンプトを含む）。
        output_schema: 構造化出力スキーマ。
        model_id: model_catalog が解決した実モデル ID。
        model: ``AgentUsage`` に記録するモデルエイリアス（呼び出し元のリクエスト由来）。
        parse: LLM 応答テキストをパースする関数。失敗時は ``AgentResponseParseError`` を raise する契約。
        log_label: デバッグ・警告ログの接頭辞（例: "Agent" / "ドラフト" / "PDF 抽出" / "表示名提案"）。

    Returns:
        ``(parse の戻り値, 合算使用量)`` のタプル。

    Raises:
        AgentResponseParseError: 2 回目もパース/スキーマ検証に失敗（``usage`` を付与して再送出）。
        LLMError: LLM 呼び出し自体の失敗（1 回目はそのまま伝播。リトライ呼び出しの失敗は
            ``usage`` を付与して再送出）。
    """
    # リトライしても 1 回目の API 原価は発生しているため、使用量は全呼び出しの合算で記録する（観測用）
    input_tokens = 0
    output_tokens = 0

    def _usage() -> AgentUsage:
        return AgentUsage(model=model, input_tokens=input_tokens, output_tokens=output_tokens)

    async def _generate_and_account(call_messages: list[dict[str, str]], *, label: str):
        """LLM を呼び出し、合算トークンへ加算してから生応答を返す。

        観測用（ADR-0023 で課金撤去）のため、初回・リトライの両方でトークン加算経路を
        この 1 箇所に集約する。``client.generate`` が失敗した場合は加算前に例外が伝播し、
        呼び出し元で確定済みの合算使用量を載せて再 raise する（使用量の二重計上を防ぐ）。
        """
        nonlocal input_tokens, output_tokens
        call_result = await client.generate(system_prompt, call_messages, output_schema, model_id)
        input_tokens += call_result.input_tokens
        output_tokens += call_result.output_tokens
        logger.debug("%s LLM %s応答（パース前）: len=%d", log_label, label, len(call_result.text))
        return call_result

    # 1 回目の呼び出し。パースまで成功すればここで確定して返す。
    result = await _generate_and_account(messages, label="生")
    try:
        parsed = parse(result.text)
        return parsed, _usage()
    except AgentResponseParseError as exc:
        # スキーマ違反応答は 1 回だけリトライする。バリデーションエラーの内容を
        # フィードバックして再生成させ、2 回目も失敗したらそのまま raise
        # （router で 502 + AGENT_PARSE_ERROR にマッピングされる既存契約を維持）
        logger.warning(
            "%s LLM 応答が出力契約に違反したためリトライ: %s", log_label, type(exc).__name__
        )
        retry_messages = [
            *messages,
            {"role": "assistant", "content": result.text},
            _build_retry_feedback(exc),
        ]

    # リトライ呼び出し（1 回のみ）。以降は失敗時も合算使用量を載せて伝播する。
    try:
        result = await _generate_and_account(retry_messages, label="リトライ")
    except LLMError as retry_exc:
        # リトライ呼び出し自体が失敗。合算した使用量（観測用）を載せて伝播する（ADR-0023 で課金撤去）
        retry_exc.usage = _usage()
        raise
    try:
        parsed = parse(result.text)
    except AgentResponseParseError as retry_exc:
        # 2 回目も失敗。合算した使用量（観測用）を載せて伝播する（ADR-0023 で課金撤去）
        raise AgentResponseParseError(str(retry_exc), usage=_usage()) from retry_exc
    return parsed, _usage()
