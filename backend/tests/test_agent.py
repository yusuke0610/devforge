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
    """テスト用の LLM クライアント（固定応答 or 例外）。受信した入力を記録する。"""

    def __init__(self, response: str | None = None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.received_system_prompt: str | None = None
        self.received_messages: list[dict[str, str]] | None = None

    async def generate(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        self.received_system_prompt = system_prompt
        self.received_messages = messages
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


def test_chat_normalizes_out_of_scope_operations(client: TestClient, monkeypatch) -> None:
    """契約: スコープ外フィールドの operation はスコープの既定 field に正規化される。"""
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
    assert [op["field"] for op in ops] == ["career_summary", "career_summary"]
    assert [op["value"] for op in ops] == ["スコープ外の提案", "スコープ内の提案"]


def test_chat_requires_prompt(client: TestClient, monkeypatch) -> None:
    """バリデーション: prompt 未指定は 422。LLM は呼ばれない。"""
    fake = _mock_llm(monkeypatch, response=_llm_json("self_pr", "提案"))
    headers = auth_header(client, "agentuser")
    resp = client.post(
        "/api/agent/chat",
        json={"scope": "self_pr", "resume": _resume_payload()},
        headers=headers,
    )
    assert resp.status_code == 422
    assert fake.received_messages is None


def test_chat_ambiguous_input_returns_llm_suggestions(client: TestClient, monkeypatch) -> None:
    """契約: 曖昧入力時、LLM が返した suggestions（依頼文候補）がそのまま返る。"""
    _mock_llm(
        monkeypatch,
        response=json.dumps(
            {
                "message": "どの方向で改善しますか？",
                "operations": [],
                "suggestions": ["300字に要約して", "成果を強調して書き直して"],
            },
            ensure_ascii=False,
        ),
    )
    headers = auth_header(client, "agentuser")
    resp = client.post(
        "/api/agent/chat",
        json={"scope": "self_pr", "prompt": "いい感じにして", "resume": _resume_payload()},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["operations"] == []
    assert body["suggestions"] == ["300字に要約して", "成果を強調して書き直して"]


def test_parse_response_discards_invalid_suggestions() -> None:
    """suggestions の検証: 空文字・200字超は破棄し、4 件を超えた分は切り詰める。"""
    raw = json.dumps(
        {
            "message": "確認です",
            "operations": [],
            "suggestions": ["", "A" * 201, "候補1", "候補2", "候補3", "候補4", "候補5"],
        },
        ensure_ascii=False,
    )
    result = _parse_response(raw, "self_pr")
    assert result.suggestions == ["候補1", "候補2", "候補3", "候補4"]


def test_parse_response_drops_suggestions_when_operations_present() -> None:
    """suggestions は operations が空のときのみ返す（同時提示しない契約）。"""
    raw = json.dumps(
        {
            "message": "提案です",
            "operations": [{"field": "self_pr", "value": "改善案"}],
            "suggestions": ["別の候補"],
        },
        ensure_ascii=False,
    )
    result = _parse_response(raw, "self_pr")
    assert len(result.operations) == 1
    assert result.suggestions == []


def test_chat_without_suggestions_field_defaults_empty(client: TestClient, monkeypatch) -> None:
    """後方互換: LLM が suggestions を返さなくても空配列として扱う。"""
    _mock_llm(monkeypatch, response=_llm_json("self_pr", "提案"))
    headers = auth_header(client, "agentuser")
    resp = client.post(
        "/api/agent/chat",
        json={"scope": "self_pr", "prompt": "改善して", "resume": _resume_payload()},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


@pytest.mark.parametrize(
    ("scope", "field", "target"),
    [
        ("career_summary", "career_summary", None),
        ("self_pr", "self_pr", None),
        (
            "project",
            "description",
            {"experience_index": 0, "client_index": 0, "project_index": 0},
        ),
    ],
)
def test_chat_system_prompt_is_scope_specific(
    client: TestClient, monkeypatch, scope: str, field: str, target: dict | None
) -> None:
    """契約: system prompt は base＋該当スコープの md のみで構成される。

    他スコープの品質基準が混ざると小型 LLM が文字数制限等を取り違えるため、
    自スコープの見出しを含み、他スコープの見出しを含まないことを検証する。
    """
    fake = _mock_llm(monkeypatch, response=_llm_json(field, "提案"))
    headers = auth_header(client, "agentuser")
    payload: dict = {"scope": scope, "prompt": "改善して", "resume": _resume_payload()}
    if target is not None:
        payload["target"] = target
    resp = client.post("/api/agent/chat", json=payload, headers=headers)
    assert resp.status_code == 200
    prompt = fake.received_system_prompt
    assert prompt is not None
    # 共通ルール（agent_base.md）が含まれる
    assert "# 共通ルール" in prompt
    # スコープ見出し（agent_{scope}.md 冒頭）は自スコープのみ
    scope_headings = {
        "career_summary": "# スコープ: 職務要約（career_summary）",
        "self_pr": "# スコープ: 自己PR（self_pr）",
        "project": "# スコープ: プロジェクト詳細（project）",
    }
    assert scope_headings[scope] in prompt
    for other, heading in scope_headings.items():
        if other != scope:
            assert heading not in prompt
    # プレースホルダはロード時に埋め込み済み（残骸が無い）
    assert "{allowed_fields}" not in prompt
    assert "{field_limits}" not in prompt
    assert field in prompt


def test_chat_passes_history_to_llm(client: TestClient, monkeypatch) -> None:
    """契約: history が LLM の messages に展開され、末尾が今回の user prompt になる。"""
    fake = _mock_llm(monkeypatch, response=_llm_json("self_pr", "提案"))
    headers = auth_header(client, "agentuser")
    history = [
        {"role": "user", "text": "自己PRを改善して"},
        {"role": "assistant", "text": '{"message": "改善しました", "operations": []}'},
    ]
    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "self_pr",
            "prompt": "もっと短くして",
            "resume": _resume_payload(),
            "history": history,
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert fake.received_messages is not None
    assert [m["role"] for m in fake.received_messages] == ["user", "assistant", "user"]
    assert fake.received_messages[0]["content"] == "自己PRを改善して"
    assert fake.received_messages[1]["content"] == history[1]["text"]
    # 末尾の今回ターンにのみレジュメコンテキストが載る
    assert "もっと短くして" in fake.received_messages[2]["content"]
    assert "self_pr" in fake.received_messages[2]["content"]


def test_chat_without_history_sends_single_message(client: TestClient, monkeypatch) -> None:
    """history 省略時は従来どおり user メッセージ 1 件のみが LLM に渡る。"""
    fake = _mock_llm(monkeypatch, response=_llm_json("self_pr", "提案"))
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
    assert resp.status_code == 200
    assert fake.received_messages is not None
    assert [m["role"] for m in fake.received_messages] == ["user"]


def test_chat_rejects_history_over_limit(client: TestClient, monkeypatch) -> None:
    """history は 6 エントリ（3 往復）まで。超過は 422。"""
    _mock_llm(monkeypatch, response=_llm_json("self_pr", "提案"))
    headers = auth_header(client, "agentuser")
    history = [{"role": "user", "text": f"依頼{i}"} for i in range(7)]
    resp = client.post(
        "/api/agent/chat",
        json={
            "scope": "self_pr",
            "prompt": "改善して",
            "resume": _resume_payload(),
            "history": history,
        },
        headers=headers,
    )
    assert resp.status_code == 422


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


def test_parse_response_normalizes_unknown_field_name() -> None:
    """許可リスト外の field 名（コンテキストの日本語キー流用など）は既定 field に正規化される。

    field は Literal ではなく str で受けるため、逸脱 operation が混ざっても
    レスポンス全体は ValidationError にならない（502 多発の再発防止）。
    """
    raw = json.dumps(
        {
            "message": "改善案です。",
            "operations": [
                {"field": "現在の自己PR", "value": "逸脱した提案"},
                {"field": "self_pr", "value": "正しい提案"},
            ],
        },
        ensure_ascii=False,
    )
    result = _parse_response(raw, "self_pr")
    assert result.message == "改善案です。"
    assert [op.field for op in result.operations] == ["self_pr", "self_pr"]
    assert [op.value for op in result.operations] == ["逸脱した提案", "正しい提案"]


def test_parse_response_project_normalizes_to_description() -> None:
    """project スコープの許可外 field は description に正規化される（role は明示時のみ）。"""
    raw = json.dumps(
        {
            "message": "改善案です。",
            "operations": [
                {"field": "プロジェクト詳細", "value": "詳細の提案"},
                {"field": "role", "value": "役割の提案"},
            ],
        },
        ensure_ascii=False,
    )
    result = _parse_response(raw, "project")
    assert [op.field for op in result.operations] == ["description", "role"]


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
