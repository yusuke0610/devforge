"""GoogleClient / OpenAIClient の単体テスト（ADR-0013）。

SDK は AsyncMock でモックし、実 API は呼ばない。検証項目:
- API キー未設定で LLMError
- スキーマが各プロバイダの構造化出力パラメータに渡る
- 実トークン使用量が LLMResult に乗る
- プロバイダ例外が LLMError にラップされる
- output_schema.to_portable_schema が oneOf/const/maxLength を除去・enum 化する

本リポジトリは pytest-asyncio を使わないため、コルーチンは asyncio.run で駆動する。
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
