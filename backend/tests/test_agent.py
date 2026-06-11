"""Agent チャットエンドポイント（POST /api/agent/chat）の統合テスト（ADR-0010）。

LLM（外部 API）のみモックし、リクエスト検証・エラーマッピング・operations の
スコープ整合フィルタは実コードを通す。
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from app.services.agent import chat_service
from app.services.agent.chat_service import (
    AgentResponseParseError,
    AgentTargetNotFoundError,
    _parse_response,
)
from app.services.agent.llm.base import LLMClient, LLMError
from fastapi.testclient import TestClient

from conftest import auth_header


class _FakeLLM(LLMClient):
    """テスト用の LLM クライアント（固定応答 or 例外）。"""

    def __init__(self, response: str | None = None, error: Exception | None = None):
        self._response = response
        self._error = error

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self._error:
            raise self._error
        assert self._response is not None
        return self._response


def _mock_llm(monkeypatch, *, response: str | None = None, error: Exception | None = None):
    fake = _FakeLLM(response=response, error=error)
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: fake)
    return fake


def _resume_payload() -> dict:
    return {
        "career_summary": "Web エンジニアとして5年の経験。",
        "self_pr": "粘り強く課題解決に取り組みます。",
        "experiences": [
            {
                "company": "株式会社テスト",
                "business_description": "受託開発",
                "clients": [
                    {
                        "name": "クライアントA",
                        "projects": [
                            {
                                "name": "EC サイト構築",
                                "role": "バックエンド開発",
                                "description": "API 設計と実装を担当。",
                                "technology_stacks": [
                                    {"category": "language", "name": "Python"}
                                ],
                                "phases": ["詳細設計", "実装"],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _llm_json(field: str, value: str, message: str = "改善案です。") -> str:
    return json.dumps(
        {"message": message, "operations": [{"field": field, "value": value}]},
        ensure_ascii=False,
    )


def test_chat_career_summary_success(client: TestClient, monkeypatch) -> None:
    """正常系: career_summary スコープで operations が返る。"""
    _mock_llm(monkeypatch, response=_llm_json("career_summary", "改善された職務要約。"))
    headers = auth_header(client, "agentuser")

    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "career_summary",
            "prompt": "職務要約をより具体的にしてください",
            "resume": _resume_payload(),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "改善案です。"
    assert body["operations"] == [
        {"field": "career_summary", "value": "改善された職務要約。"}
    ]


def test_chat_project_success(client: TestClient, monkeypatch) -> None:
    """正常系: project スコープ + target 指定で operations が返る。"""
    _mock_llm(monkeypatch, response=_llm_json("description", "改善されたプロジェクト詳細。"))
    headers = auth_header(client, "agentuser")

    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "project",
            "prompt": "成果がより伝わる詳細にしてください",
            "resume": _resume_payload(),
            "target": {"experience_index": 0, "client_index": 0, "project_index": 0},
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["operations"][0]["field"] == "description"


def test_chat_requires_auth(client: TestClient) -> None:
    """認可: 未認証は 401。"""
    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "career_summary",
            "prompt": "test",
            "resume": _resume_payload(),
        },
    )
    assert resp.status_code == 401


def test_chat_project_scope_requires_target(client: TestClient) -> None:
    """バリデーション: project スコープで target 欠落は 422（日本語メッセージ）。"""
    headers = auth_header(client, "agentuser")
    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "project",
            "prompt": "改善して",
            "resume": _resume_payload(),
        },
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_chat_target_index_out_of_range(client: TestClient, monkeypatch) -> None:
    """バリデーション: target インデックス範囲外は 422 + VALIDATION_ERROR。"""
    _mock_llm(monkeypatch, response=_llm_json("description", "x"))
    headers = auth_header(client, "agentuser")
    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "project",
            "prompt": "改善して",
            "resume": _resume_payload(),
            "target": {"experience_index": 0, "client_index": 0, "project_index": 9},
        },
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert "プロジェクトが見つかりません" in body["message"]


def test_chat_llm_failure_returns_502(client: TestClient, monkeypatch) -> None:
    """失敗系: LLMError は 502 + AGENT_LLM_ERROR（日本語メッセージ）。"""
    _mock_llm(monkeypatch, error=LLMError("timeout"))
    headers = auth_header(client, "agentuser")
    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "self_pr",
            "prompt": "改善して",
            "resume": _resume_payload(),
        },
        headers=headers,
    )
    assert resp.status_code == 502
    body = resp.json()
    assert body["code"] == "AGENT_LLM_ERROR"
    assert "AI の応答取得に失敗" in body["message"]


def test_chat_invalid_json_returns_502(client: TestClient, monkeypatch) -> None:
    """失敗系: LLM が不正 JSON を返したら 502 + AGENT_PARSE_ERROR。"""
    _mock_llm(monkeypatch, response="すみません、JSON では返せません。")
    headers = auth_header(client, "agentuser")
    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "self_pr",
            "prompt": "改善して",
            "resume": _resume_payload(),
        },
        headers=headers,
    )
    assert resp.status_code == 502
    assert resp.json()["code"] == "AGENT_PARSE_ERROR"


def test_chat_discards_out_of_scope_operations(client: TestClient, monkeypatch) -> None:
    """契約: スコープ外フィールドの operation は破棄され、message は返る。"""
    response = json.dumps(
        {
            "message": "提案です。",
            "operations": [
                {"field": "self_pr", "value": "スコープ外の提案"},
                {"field": "career_summary", "value": "スコープ内の提案"},
            ],
        },
        ensure_ascii=False,
    )
    _mock_llm(monkeypatch, response=response)
    headers = auth_header(client, "agentuser")
    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "career_summary",
            "prompt": "改善して",
            "resume": _resume_payload(),
        },
        headers=headers,
    )
    assert resp.status_code == 200
    ops = resp.json()["operations"]
    assert len(ops) == 1
    assert ops[0]["field"] == "career_summary"


# --- ユニットテスト（service 層） ---


def test_parse_response_strips_code_fence() -> None:
    """小型モデルが付けるコードフェンスを除去してパースできる。"""
    raw = "```json\n" + _llm_json("self_pr", "提案") + "\n```"
    result = _parse_response(raw, "self_pr")
    assert result.operations[0].value == "提案"


def test_parse_response_discards_over_limit_value() -> None:
    """文字数上限（role: 200）を超える operation は破棄される。"""
    raw = json.dumps(
        {"message": "m", "operations": [{"field": "role", "value": "あ" * 201}]},
        ensure_ascii=False,
    )
    result = _parse_response(raw, "project")
    assert result.operations == []


def test_parse_response_invalid_schema_raises() -> None:
    """operations の形式不正は AgentResponseParseError。"""
    with pytest.raises(AgentResponseParseError):
        _parse_response('{"message": 1, "operations": "x"}', "self_pr")


def test_factory_rejects_unknown_provider(monkeypatch) -> None:
    """設定ミス（未対応プロバイダ）は LLMError で fail fast。"""
    from app.services.agent.llm import factory

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    with pytest.raises(LLMError, match="LLM_PROVIDER"):
        factory.get_llm_client()


def test_run_agent_chat_target_not_found(monkeypatch) -> None:
    """target 範囲外は LLM を呼ぶ前に AgentTargetNotFoundError。"""
    from app.schemas.agent import AgentChatRequest

    called = AsyncMock()
    monkeypatch.setattr(chat_service, "get_llm_client", lambda: called)
    request = AgentChatRequest.model_validate(
        {
            "scope": "project",
            "prompt": "改善して",
            "resume": {"experiences": []},
            "target": {"experience_index": 0, "client_index": 0, "project_index": 0},
        }
    )
    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(AgentTargetNotFoundError):
            loop.run_until_complete(chat_service.run_agent_chat(request))
    finally:
        loop.close()
    called.generate.assert_not_called()
