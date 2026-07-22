"""AnthropicClient / OllamaClient の単体テスト（ADR-0023 で Haiku + Ollama 構成に縮退）。

SDK は AsyncMock でモックし、実 API は呼ばない。検証項目:
- API キー未設定で LLMError
- スキーマが各プロバイダの構造化出力パラメータに渡る
- 実トークン使用量が LLMResult に乗る
- プロバイダ例外が LLMError にラップされる
- 空応答・想定外応答が LLMError に倒れる
- output_schema.to_portable_schema が oneOf/const/maxLength を除去・enum 化する

本リポジトリは pytest-asyncio を使わないため、コルーチンは asyncio.run で駆動する。
"""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.services.agent.llm.base import LLMError
from app.services.agent.output_schema import build_output_schema, to_portable_schema

# ---- to_portable_schema ----


def test_to_portable_schema_flattens_oneof_to_enum() -> None:
    """operations.items の oneOf 分岐が field の enum を持つ単一オブジェクトに畳まれる。"""
    portable = to_portable_schema(build_output_schema("project"))
    items = portable["properties"]["operations"]["items"]
    assert "oneOf" not in items
    assert set(items["properties"]["field"]["enum"]) == {"description", "role"}
    assert items["properties"]["value"]["type"] == "string"


def test_to_portable_schema_strips_constraints() -> None:
    """maxLength / maxItems が再帰的に除去される（実強制は _parse_response 側）。"""
    portable = to_portable_schema(build_output_schema("career_summary"))
    assert "maxItems" not in portable["properties"]["suggestions"]
    suggestion_items = portable["properties"]["suggestions"]["items"]
    assert "maxLength" not in suggestion_items


# ---- base ヘルパ（LLMError 契約の SSoT） ----


def test_require_api_key_passes_through_and_raises() -> None:
    """非空はそのまま返し、空は label 付きで LLMError。"""
    from app.services.agent.llm.base import require_api_key

    assert require_api_key("k", "ANTHROPIC_API_KEY") == "k"
    with pytest.raises(LLMError, match="OPENAI_API_KEY が設定されていません"):
        require_api_key("", "OPENAI_API_KEY")


def test_wrap_api_error_formats_message_with_type_name() -> None:
    """provider 名と例外型名を含む LLMError を返す（raise はしない / 値を含めない）。"""
    from app.services.agent.llm.base import wrap_api_error

    err = wrap_api_error("Google", ValueError("secret-token"))
    assert isinstance(err, LLMError)
    assert str(err) == "Google API error: ValueError"
    assert "secret-token" not in str(err)


def test_require_text_passes_through_and_raises() -> None:
    """非空はそのまま返し、空 / None は LLMError（空応答ガード）。"""
    from app.services.agent.llm.base import require_text

    assert require_text("OpenAI", "hi") == "hi"
    with pytest.raises(LLMError, match="空の応答"):
        require_text("OpenAI", None)
    with pytest.raises(LLMError, match="空の応答"):
        require_text("Google", "")


# ---- AnthropicClient ----


def _patch_anthropic(monkeypatch, *, response=None, error=None) -> MagicMock:
    """anthropic.AsyncAnthropicVertex をモックし、messages.create を差し替える。"""
    from app.services.agent.llm import anthropic_client

    # Vertex 化（ADR-0015）後はキーではなく GCP プロジェクト + ロケーションで初期化する
    monkeypatch.setattr(
        anthropic_client.settings, "get_gcp_project_id", lambda: "test-project"
    )
    monkeypatch.setattr(
        anthropic_client.settings,
        "get_vertex_anthropic_location",
        lambda: "asia-southeast1",
    )
    create = AsyncMock(side_effect=error) if error else AsyncMock(return_value=response)
    fake_client = MagicMock()
    fake_client.messages.create = create
    monkeypatch.setattr(
        anthropic_client, "AsyncAnthropicVertex", lambda **kwargs: fake_client
    )
    return create


def test_anthropic_client_returns_text_and_usage(monkeypatch) -> None:
    """tool_use ブロックの input を JSON 文字列化し、実トークン使用量を返す。"""
    from app.services.agent.llm.anthropic_client import AnthropicClient

    block = SimpleNamespace(
        type="tool_use", input={"message": "ok", "operations": [], "suggestions": []}
    )
    response = SimpleNamespace(
        content=[block],
        usage=SimpleNamespace(input_tokens=110, output_tokens=22),
    )
    _patch_anthropic(monkeypatch, response=response)
    client = AnthropicClient()
    result = asyncio.run(
        client.generate("sys", [{"role": "user", "content": "hi"}],
                        build_output_schema("project"), "claude-haiku-4-5")
    )
    assert result.input_tokens == 110
    assert result.output_tokens == 22
    # text は tool input の再シリアライズ JSON（履歴契約を維持）
    assert json.loads(result.text) == block.input


def test_anthropic_client_missing_project_raises(monkeypatch) -> None:
    """GCP_PROJECT_ID 未設定は LLMError（Vertex 認証の前提が無い / ADR-0015）。"""
    from app.services.agent.llm import anthropic_client
    from app.services.agent.llm.anthropic_client import AnthropicClient

    monkeypatch.setattr(
        anthropic_client.settings, "get_gcp_project_id", lambda: ""
    )
    with pytest.raises(LLMError, match="GCP_PROJECT_ID"):
        AnthropicClient()


def test_anthropic_client_wraps_api_error(monkeypatch) -> None:
    """プロバイダ例外（タイムアウト等）は LLMError にラップされる。"""
    import anthropic
    from app.services.agent.llm.anthropic_client import AnthropicClient

    err = anthropic.APITimeoutError(request=httpx.Request("POST", "http://test"))
    _patch_anthropic(monkeypatch, error=err)
    client = AnthropicClient()
    with pytest.raises(LLMError, match="Anthropic API error"):
        asyncio.run(
            client.generate("s", [{"role": "user", "content": "x"}],
                            build_output_schema("self_pr"), "claude-haiku-4-5")
        )


def test_anthropic_client_no_tool_use_block_raises(monkeypatch) -> None:
    """tool_use ブロックが無い応答は LLMError（回帰しやすい分岐）。"""
    from app.services.agent.llm.anthropic_client import AnthropicClient

    response = SimpleNamespace(
        content=[SimpleNamespace(type="text")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=0),
    )
    _patch_anthropic(monkeypatch, response=response)
    client = AnthropicClient()
    with pytest.raises(LLMError, match="tool_use"):
        asyncio.run(
            client.generate("s", [{"role": "user", "content": "x"}],
                            build_output_schema("self_pr"), "claude-haiku-4-5")
        )


# ---- OllamaClient ----


class _FakeResponse:
    """httpx.Response の最小スタブ（raise_for_status / json のみ）。"""

    def __init__(self, json_data=None, *, status_error=None) -> None:
        self._json = json_data
        self._status_error = status_error

    def raise_for_status(self) -> None:
        if self._status_error is not None:
            raise self._status_error

    def json(self):
        if isinstance(self._json, Exception):
            raise self._json
        return self._json


class _FakeAsyncClient:
    """httpx.AsyncClient の async context manager スタブ。"""

    def __init__(self, *, response=None, post_error=None) -> None:
        self._response = response
        self._post_error = post_error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def post(self, url, json=None):
        if self._post_error is not None:
            raise self._post_error
        return self._response


def _patch_ollama(monkeypatch, *, response=None, post_error=None) -> None:
    """settings と httpx.AsyncClient をモックする。"""
    from app.services.agent.llm import ollama_client

    monkeypatch.setattr(ollama_client.settings, "get_ollama_base_url", lambda: "http://x")
    monkeypatch.setattr(ollama_client.settings, "get_ollama_model", lambda: "llama3.2")
    monkeypatch.setattr(
        ollama_client.settings, "get_ollama_timeout_seconds", lambda: 1.0
    )
    monkeypatch.setattr(
        ollama_client.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(response=response, post_error=post_error),
    )


def test_ollama_client_returns_text_with_zero_usage(monkeypatch) -> None:
    """message.content を返し、トークン使用量は 0（ローカルは無料 / ADR-0012）。"""
    from app.services.agent.llm.ollama_client import OllamaClient

    fake = _FakeResponse({"message": {"content": '{"message":"ok"}'}})
    _patch_ollama(monkeypatch, response=fake)
    result = asyncio.run(
        OllamaClient().generate("sys", [{"role": "user", "content": "hi"}],
                                build_output_schema("self_pr"), "ignored")
    )
    assert result.text == '{"message":"ok"}'
    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_ollama_client_sends_portable_schema(monkeypatch) -> None:
    """format には移植スキーマを渡す（llama.cpp の文法変換が maxLength/maxItems/oneOf で
    失敗するため）。oneOf は enum へ畳まれ、maxLength / maxItems は除去される。"""
    import json as _json

    from app.services.agent.llm import ollama_client
    from app.services.agent.llm.ollama_client import OllamaClient

    captured: dict = {}

    class _CapturingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> bool:
            return False

        async def post(self, url, json=None):
            captured["payload"] = json
            return _FakeResponse({"message": {"content": '{"message":"ok"}'}})

    monkeypatch.setattr(ollama_client.settings, "get_ollama_base_url", lambda: "http://x")
    monkeypatch.setattr(ollama_client.settings, "get_ollama_model", lambda: "llama3.2")
    monkeypatch.setattr(ollama_client.settings, "get_ollama_timeout_seconds", lambda: 1.0)
    monkeypatch.setattr(
        ollama_client.httpx, "AsyncClient", lambda **kwargs: _CapturingClient()
    )

    asyncio.run(
        OllamaClient().generate(
            "sys", [{"role": "user", "content": "hi"}],
            build_output_schema("project"), "ignored"
        )
    )

    fmt = captured["payload"]["format"]
    serialized = _json.dumps(fmt)
    # 数値制約と oneOf が文法変換を壊すため、いずれも format に残ってはいけない
    assert "maxLength" not in serialized
    assert "maxItems" not in serialized
    assert "oneOf" not in serialized
    # project の許可 field（description / role）は enum に畳まれている
    item = fmt["properties"]["operations"]["items"]
    assert item["properties"]["field"]["enum"] == ["description", "role"]


def test_ollama_client_http_error_wrapped(monkeypatch) -> None:
    """httpx.HTTPError は LLMError にラップされる。"""
    from app.services.agent.llm.ollama_client import OllamaClient

    _patch_ollama(monkeypatch, post_error=httpx.HTTPError("boom"))
    with pytest.raises(LLMError, match="Ollama API error"):
        asyncio.run(
            OllamaClient().generate("s", [{"role": "user", "content": "x"}],
                                    build_output_schema("self_pr"), "ignored")
        )


def test_ollama_client_non_dict_response_raises(monkeypatch) -> None:
    """dict 以外の応答（配列等）は LLMError（502 へ倒す）。"""
    from app.services.agent.llm.ollama_client import OllamaClient

    fake = _FakeResponse(["unexpected"])
    _patch_ollama(monkeypatch, response=fake)
    with pytest.raises(LLMError, match="想定外の形式"):
        asyncio.run(
            OllamaClient().generate("s", [{"role": "user", "content": "x"}],
                                    build_output_schema("self_pr"), "ignored")
        )


def test_ollama_client_non_dict_message_raises(monkeypatch) -> None:
    """message が dict でない応答（エラー時の文字列等）は LLMError（502 へ倒す）。"""
    from app.services.agent.llm.ollama_client import OllamaClient

    fake = _FakeResponse({"message": "boom"})
    _patch_ollama(monkeypatch, response=fake)
    with pytest.raises(LLMError, match="想定外の形式"):
        asyncio.run(
            OllamaClient().generate("s", [{"role": "user", "content": "x"}],
                                    build_output_schema("self_pr"), "ignored")
        )


def test_ollama_client_empty_content_raises(monkeypatch) -> None:
    """message.content が空の応答は LLMError（空応答ガード）。"""
    from app.services.agent.llm.ollama_client import OllamaClient

    fake = _FakeResponse({"message": {"content": ""}})
    _patch_ollama(monkeypatch, response=fake)
    with pytest.raises(LLMError, match="空の応答"):
        asyncio.run(
            OllamaClient().generate("s", [{"role": "user", "content": "x"}],
                                    build_output_schema("self_pr"), "ignored")
        )
