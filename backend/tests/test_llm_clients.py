"""AnthropicClient / GoogleClient / OpenAIClient / OllamaClient の単体テスト（ADR-0013）。

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


# ---- GoogleClient ----


def _patch_google(monkeypatch, *, response=None, error=None) -> MagicMock:
    """google.genai.Client をモックし、aio.models.generate_content を差し替える。"""
    from app.services.agent.llm import google_client

    monkeypatch.setattr(google_client.settings, "get_google_api_key", lambda: "test-key")
    gen = AsyncMock(side_effect=error) if error else AsyncMock(return_value=response)
    fake_client = MagicMock()
    fake_client.aio.models.generate_content = gen
    monkeypatch.setattr(google_client.genai, "Client", lambda **kwargs: fake_client)
    return gen


def test_google_client_returns_text_and_usage(monkeypatch) -> None:
    """応答テキストと実トークン使用量を LLMResult で返す。"""
    from app.services.agent.llm.google_client import GoogleClient

    response = SimpleNamespace(
        text='{"message":"ok","operations":[],"suggestions":[]}',
        usage_metadata=SimpleNamespace(prompt_token_count=120, candidates_token_count=45),
    )
    gen = _patch_google(monkeypatch, response=response)
    client = GoogleClient()
    result = asyncio.run(
        client.generate("sys", [{"role": "user", "content": "hi"}],
                        build_output_schema("self_pr"), "gemini-2.5-flash")
    )
    assert result.input_tokens == 120
    assert result.output_tokens == 45
    # response_schema に移植済みスキーマ（oneOf なし）が渡っている
    config = gen.await_args.kwargs["config"]
    assert "oneOf" not in str(config.response_schema)
    # Gemini は additionalProperties 非対応のため除去されている
    assert "additionalProperties" not in str(config.response_schema)


def test_google_client_missing_key_raises(monkeypatch) -> None:
    """GOOGLE_API_KEY 未設定は LLMError。"""
    from app.services.agent.llm import google_client
    from app.services.agent.llm.google_client import GoogleClient

    monkeypatch.setattr(google_client.settings, "get_google_api_key", lambda: "")
    with pytest.raises(LLMError, match="GOOGLE_API_KEY"):
        GoogleClient()


def test_google_client_wraps_api_error(monkeypatch) -> None:
    """プロバイダ例外は LLMError にラップされる。"""
    from app.services.agent.llm import google_client
    from app.services.agent.llm.google_client import GoogleClient

    err = google_client.genai_errors.APIError(400, "BAD_REQUEST", "boom")
    _patch_google(monkeypatch, error=err)
    client = GoogleClient()
    with pytest.raises(LLMError, match="Google API error"):
        asyncio.run(
            client.generate("s", [{"role": "user", "content": "x"}],
                            build_output_schema("self_pr"), "gemini-2.5-flash")
        )


# ---- OpenAIClient ----


def _patch_openai(monkeypatch, *, response=None, error=None) -> MagicMock:
    """openai.AsyncOpenAI をモックし、chat.completions.create を差し替える。"""
    from app.services.agent.llm import openai_client

    monkeypatch.setattr(openai_client.settings, "get_openai_api_key", lambda: "test-key")
    create = AsyncMock(side_effect=error) if error else AsyncMock(return_value=response)
    fake_client = MagicMock()
    fake_client.chat.completions.create = create
    monkeypatch.setattr(openai_client.openai, "AsyncOpenAI", lambda **kwargs: fake_client)
    return create


def test_openai_client_returns_text_and_usage(monkeypatch) -> None:
    """応答テキストと実トークン使用量を LLMResult で返し、strict schema を渡す。"""
    from app.services.agent.llm.openai_client import OpenAIClient

    message = SimpleNamespace(content='{"message":"ok","operations":[],"suggestions":[]}')
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=200, completion_tokens=60),
    )
    create = _patch_openai(monkeypatch, response=response)
    client = OpenAIClient()
    result = asyncio.run(
        client.generate("sys", [{"role": "user", "content": "hi"}],
                        build_output_schema("project"), "gpt-4o-mini")
    )
    assert result.input_tokens == 200
    assert result.output_tokens == 60
    fmt = create.await_args.kwargs["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True
    assert "oneOf" not in str(fmt["json_schema"]["schema"])
    # OpenAI strict は additionalProperties: false が必須のため保持されている
    assert fmt["json_schema"]["schema"]["additionalProperties"] is False


def test_openai_client_missing_key_raises(monkeypatch) -> None:
    """OPENAI_API_KEY 未設定は LLMError。"""
    from app.services.agent.llm import openai_client
    from app.services.agent.llm.openai_client import OpenAIClient

    monkeypatch.setattr(openai_client.settings, "get_openai_api_key", lambda: "")
    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        OpenAIClient()


def test_openai_client_wraps_api_error(monkeypatch) -> None:
    """プロバイダ例外は LLMError にラップされる。"""
    from app.services.agent.llm import openai_client
    from app.services.agent.llm.openai_client import OpenAIClient

    err = openai_client.openai.OpenAIError("boom")
    _patch_openai(monkeypatch, error=err)
    client = OpenAIClient()
    with pytest.raises(LLMError, match="OpenAI API error"):
        asyncio.run(
            client.generate("s", [{"role": "user", "content": "x"}],
                            build_output_schema("self_pr"), "gpt-4o-mini")
        )


def test_openai_client_empty_response_raises(monkeypatch) -> None:
    """choices が空（content なし）の応答は LLMError（空応答ガード）。"""
    from app.services.agent.llm.openai_client import OpenAIClient

    response = SimpleNamespace(choices=[], usage=None)
    _patch_openai(monkeypatch, response=response)
    client = OpenAIClient()
    with pytest.raises(LLMError, match="空の応答"):
        asyncio.run(
            client.generate("s", [{"role": "user", "content": "x"}],
                            build_output_schema("self_pr"), "gpt-4o-mini")
        )


# ---- AnthropicClient ----


def _patch_anthropic(monkeypatch, *, response=None, error=None) -> MagicMock:
    """anthropic.AsyncAnthropic をモックし、messages.create を差し替える。"""
    from app.services.agent.llm import anthropic_client

    monkeypatch.setattr(
        anthropic_client.settings, "get_anthropic_api_key", lambda: "test-key"
    )
    create = AsyncMock(side_effect=error) if error else AsyncMock(return_value=response)
    fake_client = MagicMock()
    fake_client.messages.create = create
    monkeypatch.setattr(
        anthropic_client.anthropic, "AsyncAnthropic", lambda **kwargs: fake_client
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


def test_anthropic_client_missing_key_raises(monkeypatch) -> None:
    """ANTHROPIC_API_KEY 未設定は LLMError。"""
    from app.services.agent.llm import anthropic_client
    from app.services.agent.llm.anthropic_client import AnthropicClient

    monkeypatch.setattr(
        anthropic_client.settings, "get_anthropic_api_key", lambda: ""
    )
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
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
