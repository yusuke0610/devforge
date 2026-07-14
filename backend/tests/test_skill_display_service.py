"""スキル表示名提案サービス（proposer）の単体テスト（ADR-0016 D11）。

LLM のみモックし、パース・捏造メンバー破棄・重複破棄・リトライ・課金用 usage の合算は
実コードを通す。async 実行はグローバル event loop を触らない分離パターンで行う
（mutmut の clean test 対策 / .claude/rules/backend/test.md）。
"""

import asyncio
import json

import pytest
from app.services.agent.chat_service import AgentResponseParseError
from app.services.agent.llm.base import LLMClient, LLMError, LLMResult
from app.services.agent.skill_display import proposer
from app.services.agent.skill_display.output_schema import MAX_DISPLAY_NAME_LENGTH
from app.services.agent.skill_display.proposer import (
    SkillForProposal,
    propose_skill_display_names,
)


class _SequentialFakeLLM(LLMClient):
    """呼び出しごとに応答（または例外）を順に返す LLM クライアント。"""

    def __init__(self, responses: list, input_tokens: int = 10, output_tokens: int = 20):
        self._responses = list(responses)
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.calls: list[list[dict[str, str]]] = []
        self.received_output_schema: dict | None = None

    async def generate(self, system_prompt, messages, output_schema, model_id) -> LLMResult:
        self.calls.append(messages)
        self.received_output_schema = output_schema
        item = self._responses[len(self.calls) - 1]
        if isinstance(item, Exception):
            raise item
        return LLMResult(
            text=item, input_tokens=self._input_tokens, output_tokens=self._output_tokens
        )


def _mock_llm(monkeypatch, responses: list) -> _SequentialFakeLLM:
    fake = _SequentialFakeLLM(responses)
    monkeypatch.setattr(proposer, "get_llm_client", lambda provider: fake)
    return fake


def _run(coro):
    """グローバル event loop を汚さずにコルーチンを実行する。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _skills() -> list[SkillForProposal]:
    return [
        SkillForProposal(kind="language", ecosystem="", canonical_name="Python"),
        SkillForProposal(kind="package", ecosystem="npm", canonical_name="@aws-sdk/client-s3"),
        SkillForProposal(
            kind="package", ecosystem="npm", canonical_name="@aws-sdk/client-eventbridge"
        ),
        SkillForProposal(kind="infra", ecosystem="terraform", canonical_name="aws_s3_bucket"),
    ]


def test_proposal_resolves_members_to_identities(monkeypatch) -> None:
    """提案グループの member token が実在スキルの identity へ解決されること。"""
    response = json.dumps(
        {
            "groups": [
                {"display_name": "Amazon S3", "members": ["npm:@aws-sdk/client-s3"]},
                {
                    "display_name": "Amazon EventBridge",
                    "members": ["npm:@aws-sdk/client-eventbridge"],
                },
                {"display_name": "Python", "members": ["language:Python"]},
            ]
        }
    )
    _mock_llm(monkeypatch, [response])

    result = _run(propose_skill_display_names("haiku", _skills()))

    by_name = {g.display_name: g for g in result.groups}
    assert set(by_name) == {"Amazon S3", "Amazon EventBridge", "Python"}
    s3 = by_name["Amazon S3"].members
    assert len(s3) == 1
    assert s3[0].kind == "package"
    assert s3[0].ecosystem == "npm"
    assert s3[0].canonical_name == "@aws-sdk/client-s3"
    # 使用量が載ること（無料/有料に関わらず router が課金判断に使う）
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 20
    assert result.usage.model == "haiku"


def test_fabricated_member_token_is_dropped(monkeypatch) -> None:
    """許可集合に無い token（捏造）は破棄されること（動的 enum の二重防衛）。"""
    response = json.dumps(
        {
            "groups": [
                {
                    "display_name": "React",
                    "members": ["npm:react", "npm:@aws-sdk/client-s3"],
                }
            ]
        }
    )
    _mock_llm(monkeypatch, [response])

    result = _run(propose_skill_display_names("haiku", _skills()))

    # npm:react は与えていないので破棄され、実在の client-s3 のみ残る
    assert len(result.groups) == 1
    members = result.groups[0].members
    assert [m.canonical_name for m in members] == ["@aws-sdk/client-s3"]


def test_duplicate_member_assigned_once(monkeypatch) -> None:
    """同じ token を複数グループに入れても最初の 1 グループにのみ割り当てられること。"""
    response = json.dumps(
        {
            "groups": [
                {"display_name": "AWS SDK", "members": ["npm:@aws-sdk/client-s3"]},
                {"display_name": "Amazon S3", "members": ["npm:@aws-sdk/client-s3"]},
            ]
        }
    )
    _mock_llm(monkeypatch, [response])

    result = _run(propose_skill_display_names("haiku", _skills()))

    # 2 グループ目は重複割当で member が残らず破棄される
    assert [g.display_name for g in result.groups] == ["AWS SDK"]


def test_empty_and_overlong_groups_dropped(monkeypatch) -> None:
    """メンバー 0 件・表示名が上限超過のグループは破棄されること（切り詰めない）。"""
    response = json.dumps(
        {
            "groups": [
                {"display_name": "空グループ", "members": []},
                {"display_name": "X" * (MAX_DISPLAY_NAME_LENGTH + 1), "members": ["language:Python"]},
                {"display_name": "Python", "members": ["language:Python"]},
            ]
        }
    )
    _mock_llm(monkeypatch, [response])

    result = _run(propose_skill_display_names("haiku", _skills()))

    # 空グループと上限超過グループは破棄。language:Python は生き残るグループへ 1 回だけ割当
    assert [g.display_name for g in result.groups] == ["Python"]


def test_retry_recovers_after_invalid_json(monkeypatch) -> None:
    """1 回目が不正 JSON でもリトライで回復し、使用量は 2 回分合算されること。"""
    good = json.dumps(
        {"groups": [{"display_name": "Python", "members": ["language:Python"]}]}
    )
    fake = _mock_llm(monkeypatch, ["not json", good])

    result = _run(propose_skill_display_names("haiku", _skills()))

    assert len(fake.calls) == 2
    assert [g.display_name for g in result.groups] == ["Python"]
    # 1 回目 + 2 回目の API 原価を合算課金（ADR-0012）
    assert result.usage.input_tokens == 20
    assert result.usage.output_tokens == 40


def test_retry_failure_propagates_usage(monkeypatch) -> None:
    """2 回とも失敗したら合算 usage 付きの AgentResponseParseError を送出すること。"""
    fake = _mock_llm(monkeypatch, ["not json", "still not json"])

    with pytest.raises(AgentResponseParseError) as excinfo:
        _run(propose_skill_display_names("haiku", _skills()))

    assert len(fake.calls) == 2
    assert excinfo.value.usage is not None
    assert excinfo.value.usage.input_tokens == 20
    assert excinfo.value.usage.output_tokens == 40


def test_llm_error_on_retry_carries_usage(monkeypatch) -> None:
    """リトライ呼び出しが LLMError なら 1 回目分の usage を載せて伝播すること。"""
    fake = _mock_llm(monkeypatch, ["not json", LLMError("boom")])

    with pytest.raises(LLMError) as excinfo:
        _run(propose_skill_display_names("haiku", _skills()))

    assert len(fake.calls) == 2
    assert excinfo.value.usage is not None
    assert excinfo.value.usage.input_tokens == 10  # 1 回目のみ確定
