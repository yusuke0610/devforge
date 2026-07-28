"""PDF 経歴書インポートの構造化抽出サービス（import_service）の単体テスト（ADR-0024 / #527）。

LLM のみモックし、パース・リトライ・使用量の合算は実コードを通す。async 実行は
グローバル event loop を触らない分離パターンで行う（mutmut の clean test 対策 /
.claude/rules/backend/test.md）。兄弟モジュール（draft_service / proposer）の
`_SequentialFakeLLM` と同じパターンを踏襲する（BE_report_20260728_2200.md Test Review「Add」）。
"""

import asyncio
import json

import pytest
from app.services.agent.chat_service import AgentResponseParseError
from app.services.agent.llm.base import LLMClient, LLMError, LLMResult
from app.services.agent.resume_import import import_service
from app.services.agent.resume_import.import_service import run_resume_import


class _SequentialFakeLLM(LLMClient):
    """呼び出しごとに応答（または例外）を順に返す LLM クライアント。"""

    def __init__(self, responses: list, input_tokens: int = 10, output_tokens: int = 20):
        self._responses = list(responses)
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.calls: list[list[dict[str, str]]] = []

    async def generate(self, system_prompt, messages, output_schema, model_id) -> LLMResult:
        self.calls.append(messages)
        item = self._responses[len(self.calls) - 1]
        if isinstance(item, Exception):
            raise item
        return LLMResult(
            text=item, input_tokens=self._input_tokens, output_tokens=self._output_tokens
        )


def _mock_llm(monkeypatch, responses: list) -> _SequentialFakeLLM:
    fake = _SequentialFakeLLM(responses)
    monkeypatch.setattr(import_service, "get_llm_client", lambda provider: fake)
    return fake


def _run(coro):
    """グローバル event loop を汚さずにコルーチンを実行する。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _import_json(**fields) -> str:
    payload = {"full_name": "", "career_summary": "", "self_pr": "", "experiences": []}
    payload.update(fields)
    return json.dumps(payload, ensure_ascii=False)


def test_run_resume_import_success(monkeypatch) -> None:
    """1 回目の応答が正当なら、そのままパース済み payload と使用量を返すこと。"""
    response = _import_json(full_name="山田 太郎", career_summary="バックエンド 5 年。")
    fake = _mock_llm(monkeypatch, [response])

    result = _run(run_resume_import("haiku", "抽出済みテキスト"))

    assert len(fake.calls) == 1
    assert result.payload["full_name"] == "山田 太郎"
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 20
    assert result.usage.model == "haiku"


def test_run_resume_import_retry_recovers_after_invalid_json(monkeypatch) -> None:
    """1 回目が不正 JSON でもリトライで回復し、使用量は 2 回分合算されること。"""
    good = _import_json(full_name="鈴木 花子")
    fake = _mock_llm(monkeypatch, ["not json", good])

    result = _run(run_resume_import("haiku", "抽出済みテキスト"))

    assert len(fake.calls) == 2
    assert result.payload["full_name"] == "鈴木 花子"
    # リトライメッセージ（assistant の生応答 + フィードバック）が積まれていること
    retry_messages = fake.calls[1]
    assert retry_messages[-2] == {"role": "assistant", "content": "not json"}
    assert retry_messages[-1]["role"] == "user"
    assert "出力契約に違反しています" in retry_messages[-1]["content"]
    # 1 回目 + 2 回目の API 原価を合算（観測用 / ADR-0023）
    assert result.usage.input_tokens == 20
    assert result.usage.output_tokens == 40


def test_run_resume_import_retry_failure_propagates_usage(monkeypatch) -> None:
    """2 回とも失敗したら合算 usage 付きの AgentResponseParseError を送出すること。"""
    fake = _mock_llm(monkeypatch, ["not json", "still not json"])

    with pytest.raises(AgentResponseParseError) as excinfo:
        _run(run_resume_import("haiku", "抽出済みテキスト"))

    assert len(fake.calls) == 2
    assert excinfo.value.usage is not None
    assert excinfo.value.usage.input_tokens == 20
    assert excinfo.value.usage.output_tokens == 40


def test_run_resume_import_llm_error_on_retry_carries_usage(monkeypatch) -> None:
    """リトライ呼び出しが LLMError なら 1 回目分の usage を載せて伝播すること。"""
    fake = _mock_llm(monkeypatch, ["not json", LLMError("boom")])

    with pytest.raises(LLMError) as excinfo:
        _run(run_resume_import("haiku", "抽出済みテキスト"))

    assert len(fake.calls) == 2
    assert excinfo.value.usage is not None
    assert excinfo.value.usage.input_tokens == 10  # 1 回目のみ確定
