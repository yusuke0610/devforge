"""経歴書ドラフト生成サービス（draft_service）の単体テスト（ADR-0018）。

LLM のみモックし、パース・degrade・リトライ・課金用 usage の合算は実コードを通す。
async 実行はグローバル event loop を触らない分離パターンで行う
（mutmut の clean test 対策 / .claude/rules/backend/test.md）。
"""

import asyncio
import json

import pytest
from app.schemas.github_link import AnalyzedRepoSummary
from app.services.agent.chat_service import AgentResponseParseError
from app.services.agent.llm.base import LLMClient, LLMError, LLMResult
from app.services.agent.resume_draft import draft_service
from app.services.agent.resume_draft.context import DraftSource, RepoTechnology
from app.services.agent.resume_draft.draft_service import run_resume_draft
from app.services.agent.resume_draft.mapper import UnknownRepositoryError
from app.services.agent.resume_draft.output_schema import (
    MAX_PROJECT_DESCRIPTION_LENGTH,
    build_draft_output_schema,
)


class _SequentialFakeLLM(LLMClient):
    """呼び出しごとに応答（または例外）を順に返す LLM クライアント。"""

    def __init__(self, responses: list, input_tokens: int = 10, output_tokens: int = 20):
        """順に返す応答（str）または送出する例外（Exception）のリストを受け取る。"""
        self._responses = list(responses)
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self.calls: list[list[dict[str, str]]] = []
        self.received_output_schema: dict | None = None

    async def generate(self, system_prompt, messages, output_schema, model_id) -> LLMResult:
        """受信 messages を記録し、呼び出し順に対応した応答を返すか例外を送出する。"""
        self.calls.append(messages)
        self.received_output_schema = output_schema
        item = self._responses[len(self.calls) - 1]
        if isinstance(item, Exception):
            raise item
        return LLMResult(
            text=item, input_tokens=self._input_tokens, output_tokens=self._output_tokens
        )


def _mock_llm(monkeypatch, responses: list) -> _SequentialFakeLLM:
    """draft_service の LLM クライアントを差し替え、そのインスタンスを返す。"""
    fake = _SequentialFakeLLM(responses)
    monkeypatch.setattr(draft_service, "get_llm_client", lambda provider: fake)
    return fake


def _run(coro):
    """グローバル event loop を汚さずにコルーチンを実行する。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# 採用リポジトリ（ADR-0026 決定 2）。LLM は採用分のみを対象にする
_SELECTED = ["octocat/newer", "octocat/older"]


def _source() -> DraftSource:
    """リポ 2 件のテスト用 DraftSource を返す。"""
    return DraftSource(
        username="octocat",
        email="octo@example.com",
        repos=[
            AnalyzedRepoSummary(
                full_name="octocat/newer", description="新しい方",
                created_at="2024-01-01T00:00:00Z", pushed_at="2026-06-01T00:00:00Z",
            ),
            AnalyzedRepoSummary(
                full_name="octocat/older", description="古い方",
                created_at="2022-01-01T00:00:00Z", pushed_at="2024-06-01T00:00:00Z",
            ),
        ],
        repo_technologies={
            "octocat/newer": [RepoTechnology("language", "Python", 0.9, language_bytes=100)],
        },
    )


def _draft_json(descriptions: dict[str, str] | None = None, **overrides) -> str:
    """契約に沿ったドラフト応答 JSON を生成する。"""
    if descriptions is None:
        descriptions = {"octocat/newer": "新しい方の説明。", "octocat/older": "古い方の説明。"}
    data = {
        "career_summary": "生成された職務要約。",
        "self_pr": "生成された自己PR。",
        "project_descriptions": [
            {"repo_full_name": name, "description": text}
            for name, text in descriptions.items()
        ],
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def test_draft_success_merges_llm_output(monkeypatch) -> None:
    """LLM の自然文が骨格（選定順）へマージされ、usage が実測値で返る。"""
    fake = _mock_llm(monkeypatch, [_draft_json()])
    result = _run(run_resume_draft("haiku", _source(), repo_full_names=_SELECTED))

    assert result.payload["career_summary"] == "生成された職務要約。"
    assert result.payload["self_pr"] == "生成された自己PR。"
    projects = result.payload["projects"]
    # 選定順（継続期間 × 実装量。ADR-0026 決定 3）: newer → older
    assert [p["name"] for p in projects] == ["newer", "older"]
    assert projects[0]["description"] == "新しい方の説明。"
    assert projects[1]["description"] == "古い方の説明。"

    assert result.usage.model == "haiku"
    assert result.usage.input_tokens == 10
    assert result.usage.output_tokens == 20
    # 出力スキーマの enum が選定リポで縛られている（捏造リポの構造排除）
    expected_schema = build_draft_output_schema(["octocat/newer", "octocat/older"])
    assert fake.received_output_schema == expected_schema


def test_draft_limits_llm_to_selected_repositories(monkeypatch) -> None:
    """LLM の説明文生成は採用分のみ（コストが選択数に比例する / ADR-0026 決定 2）。"""
    fake = _mock_llm(monkeypatch, [_draft_json({"octocat/older": "古い方の説明。"})])
    result = _run(run_resume_draft("haiku", _source(), repo_full_names=["octocat/older"]))

    assert [p["name"] for p in result.payload["projects"]] == ["older"]
    # 出力スキーマの enum も採用分だけに縛られる（非採用リポの説明を構造的に排除）
    assert fake.received_output_schema == build_draft_output_schema(["octocat/older"])


def test_draft_rejects_repository_outside_link_data() -> None:
    """連携データに無いリポジトリの採用指定は生成前に弾く。"""
    with pytest.raises(UnknownRepositoryError):
        _run(run_resume_draft("haiku", _source(), repo_full_names=["octocat/ghost"]))


def test_draft_missing_description_falls_back_to_repo_description(monkeypatch) -> None:
    """説明が返らなかったプロジェクトは repo description のまま残す（degrade）。"""
    _mock_llm(monkeypatch, [_draft_json({"octocat/newer": "新しい方の説明。"})])
    result = _run(run_resume_draft("haiku", _source(), repo_full_names=_SELECTED))
    projects = result.payload["projects"]
    assert projects[0]["description"] == "新しい方の説明。"
    assert projects[1]["description"] == "古い方"


def test_draft_drops_unknown_repo_and_over_limit_description(monkeypatch) -> None:
    """許可外リポの説明・上限超過の説明は破棄され、フォールバックが残る（切り詰めない）。"""
    response = _draft_json(
        {
            "octocat/evil": "存在しないリポの説明。",
            "octocat/older": "あ" * (MAX_PROJECT_DESCRIPTION_LENGTH + 1),
        }
    )
    _mock_llm(monkeypatch, [response])
    result = _run(run_resume_draft("haiku", _source(), repo_full_names=_SELECTED))
    projects = result.payload["projects"]
    assert projects[0]["description"] == "新しい方"
    assert projects[1]["description"] == "古い方"


def test_draft_retries_once_with_error_feedback(monkeypatch) -> None:
    """1 回目が契約違反なら違反内容をフィードバックして 1 回だけリトライする。"""
    fake = _mock_llm(monkeypatch, ["JSON ではない応答", _draft_json()])
    result = _run(run_resume_draft("haiku", _source(), repo_full_names=_SELECTED))

    assert result.payload["career_summary"] == "生成された職務要約。"
    assert len(fake.calls) == 2
    # リトライには前回応答（assistant）と違反フィードバック（user）が含まれる
    retry_messages = fake.calls[1]
    assert retry_messages[-2]["role"] == "assistant"
    assert "出力契約に違反" in retry_messages[-1]["content"]
    # 使用量はリトライ分も合算される（課金漏れ防止 / ADR-0012）
    assert result.usage.input_tokens == 20
    assert result.usage.output_tokens == 40


def test_draft_empty_career_summary_is_contract_violation(monkeypatch) -> None:
    """career_summary の欠落は degrade せずリトライ対象の契約違反として扱う。"""
    fake = _mock_llm(monkeypatch, [_draft_json(career_summary=""), _draft_json()])
    result = _run(run_resume_draft("haiku", _source(), repo_full_names=_SELECTED))
    assert len(fake.calls) == 2
    assert result.payload["career_summary"] == "生成された職務要約。"


def test_draft_retry_failure_raises_with_accumulated_usage(monkeypatch) -> None:
    """2 回とも契約違反なら合算 usage を載せて AgentResponseParseError を送出する。"""
    _mock_llm(monkeypatch, ["不正応答 1 回目", "不正応答 2 回目"])
    with pytest.raises(AgentResponseParseError) as exc_info:
        _run(run_resume_draft("haiku", _source(), repo_full_names=_SELECTED))
    assert exc_info.value.usage is not None
    assert exc_info.value.usage.input_tokens == 20
    assert exc_info.value.usage.output_tokens == 40


def test_draft_llm_error_on_retry_carries_usage(monkeypatch) -> None:
    """リトライ呼び出し自体の失敗は 1 回目分の usage を載せて LLMError を伝播する。"""
    _mock_llm(monkeypatch, ["不正応答", LLMError("timeout")])
    with pytest.raises(LLMError) as exc_info:
        _run(run_resume_draft("haiku", _source(), repo_full_names=_SELECTED))
    assert exc_info.value.usage is not None
    assert exc_info.value.usage.input_tokens == 10
    assert exc_info.value.usage.output_tokens == 20


def test_draft_llm_error_on_first_call_propagates(monkeypatch) -> None:
    """1 回目の呼び出し失敗はトークン未消費のため usage 無しで伝播する。"""
    _mock_llm(monkeypatch, [LLMError("connection refused")])
    with pytest.raises(LLMError) as exc_info:
        _run(run_resume_draft("haiku", _source(), repo_full_names=_SELECTED))
    assert exc_info.value.usage is None
