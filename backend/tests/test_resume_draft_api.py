"""経歴書ドラフト PDF エンドポイント（POST /api/agent/resume-draft/pdf）の統合テスト（ADR-0018）。

LLM のみモックし、認可ガード・課金配線・409/502 のエラーマッピング・PDF 生成は
実コードを通す（DB は実 SQLite セッション）。
"""

import json

from app.models import GitHubLinkCache, User
from app.models.billing import AgentUsageLog
from app.models.skill import GitHubSkill, GitHubSkillEvidence
from app.schemas.github_link import GitHubLinkResponse
from app.services.agent.llm.base import LLMClient, LLMResult
from app.services.agent.resume_draft import draft_service
from fastapi.testclient import TestClient

from conftest import auth_header


class _FakeLLM(LLMClient):
    """固定応答を返すテスト用 LLM クライアント。"""

    def __init__(self, response: str, input_tokens: int = 100, output_tokens: int = 200):
        """固定応答とトークン実測値（課金記録の検証用）をセットする。"""
        self._response = response
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    async def generate(self, system_prompt, messages, output_schema, model_id) -> LLMResult:
        """固定応答を返す。"""
        return LLMResult(
            text=self._response,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
        )


def _draft_response() -> str:
    """契約に沿ったドラフト応答 JSON を返す。"""
    return json.dumps(
        {
            "career_summary": "生成された職務要約。",
            "self_pr": "生成された自己PR。",
            "project_descriptions": [
                {"repo_full_name": "octo/app", "description": "アプリの説明。"}
            ],
        },
        ensure_ascii=False,
    )


def _seed_link_data(db, username: str = "testuser", *, legacy: bool = False) -> None:
    """連携キャッシュ（+ スキル証跡）を投入する。legacy=True で repos 無しの旧形式。"""
    user = db.query(User).filter_by(username=username).one()
    result = {
        "username": username,
        "repos_analyzed": 1,
        "unique_skills": 1,
        "analyzed_at": "2026-06-01T00:00:00",
        "languages": {"Python": 1000},
    }
    if not legacy:
        result["repos"] = [
            {
                "full_name": "octo/app",
                "description": "タスク管理アプリ",
                "created_at": "2024-01-01T00:00:00Z",
                "pushed_at": "2026-06-01T00:00:00Z",
            }
        ]
        skill = GitHubSkill(user_id=user.id, kind="language", canonical_name="Python")
        skill.evidence = [
            GitHubSkillEvidence(
                repo_full_name="octo/app",
                signal_source="language_bytes",
                confidence=0.9,
                language_bytes=1000,
            )
        ]
        db.add(skill)
    db.add(GitHubLinkCache(user_id=user.id, status="completed", result=result))
    db.commit()


def test_resume_draft_pdf_success(client: TestClient, monkeypatch) -> None:
    """ハッピーパス: PDF が返り、使用ログ（無料モデルも対象）が記録される。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)
    monkeypatch.setattr(
        draft_service, "get_llm_client", lambda provider: _FakeLLM(_draft_response())
    )

    res = client.post("/api/agent/resume-draft/pdf", json={"model": "haiku"}, headers=headers)

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")

    # 課金・使用ログの配線（ADR-0012）: 無料モデルでもログのみ記録される
    (log,) = client._db_session.query(AgentUsageLog).all()
    assert log.model_alias == "haiku"
    assert log.input_tokens == 100
    assert log.output_tokens == 200
    assert log.credit_cost == 0


def test_resume_draft_pdf_requires_github_login(client: TestClient) -> None:
    """GitHub 未連携ユーザー（github_id 無し）は 403。"""
    headers = auth_header(client)
    res = client.post("/api/agent/resume-draft/pdf", json={"model": "haiku"}, headers=headers)
    assert res.status_code == 403


def test_resume_draft_pdf_requires_credits_for_paid_model(client: TestClient) -> None:
    """有料モデルは残高 0 だと LLM を呼ぶ前に 402。"""
    headers = auth_header(client, github_id=1)
    res = client.post("/api/agent/resume-draft/pdf", json={"model": "sonnet"}, headers=headers)
    assert res.status_code == 402


def test_resume_draft_pdf_conflict_without_link_cache(client: TestClient) -> None:
    """連携未実行は 409（GitHub 連携の実行を促す）。"""
    headers = auth_header(client, github_id=1)
    res = client.post("/api/agent/resume-draft/pdf", json={"model": "haiku"}, headers=headers)
    assert res.status_code == 409


def test_resume_draft_pdf_conflict_with_legacy_cache(client: TestClient) -> None:
    """repos キーを持たない旧形式キャッシュ（ADR-0018 以前の連携結果）は 409（再連携を促す）。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session, legacy=True)
    res = client.post("/api/agent/resume-draft/pdf", json={"model": "haiku"}, headers=headers)
    assert res.status_code == 409


def test_resume_draft_pdf_conflict_with_zero_repositories(client: TestClient) -> None:
    """新形式で分析対象リポジトリが 0 件（repos: []）は 409（旧形式とは別メッセージ）。"""
    headers = auth_header(client, github_id=1)
    user = client._db_session.query(User).filter_by(username="testuser").one()
    client._db_session.add(
        GitHubLinkCache(
            user_id=user.id,
            status="completed",
            result={
                "username": "testuser",
                "repos_analyzed": 0,
                "unique_skills": 0,
                "analyzed_at": "2026-06-01T00:00:00",
                "languages": {},
                "repos": [],
            },
        )
    )
    client._db_session.commit()

    res = client.post("/api/agent/resume-draft/pdf", json={"model": "haiku"}, headers=headers)
    assert res.status_code == 409
    # 旧形式（draft_link_required）ではなく 0 件専用メッセージが返る
    assert "公開リポジトリ" in res.json()["message"]


def test_resume_draft_pdf_parse_failure_returns_502(client: TestClient, monkeypatch) -> None:
    """リトライ後も契約違反なら 502（消費済みトークンの使用ログは記録される）。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)
    monkeypatch.setattr(
        draft_service, "get_llm_client", lambda provider: _FakeLLM("JSON ではない応答")
    )

    res = client.post("/api/agent/resume-draft/pdf", json={"model": "haiku"}, headers=headers)

    assert res.status_code == 502
    # 失敗パスでも 2 回分の合算トークンが記録される（課金漏れ防止 / ADR-0012）
    (log,) = client._db_session.query(AgentUsageLog).all()
    assert log.input_tokens == 200
    assert log.output_tokens == 400


def test_resume_draft_pdf_generation_failure_not_charged(
    client: TestClient, monkeypatch
) -> None:
    """PDF 生成が失敗した場合はユーザーに課金しない（使用ログも残さない / CodeRabbit 指摘）。"""
    from app.routers import agent as agent_router

    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)
    monkeypatch.setattr(
        draft_service, "get_llm_client", lambda provider: _FakeLLM(_draft_response())
    )

    def _fail_pdf(_payload):
        raise RuntimeError("PDF 生成失敗")

    monkeypatch.setattr(agent_router, "build_resume_pdf", _fail_pdf)

    res = client.post("/api/agent/resume-draft/pdf", json={"model": "haiku"}, headers=headers)

    assert res.status_code == 500
    # 課金は PDF 生成成功後にのみ行うため、使用ログは記録されない
    assert client._db_session.query(AgentUsageLog).count() == 0


def test_resume_draft_pdf_invalid_model_rejected(client: TestClient) -> None:
    """未知のモデルエイリアスはスキーマ検証で 422。"""
    headers = auth_header(client, github_id=1)
    res = client.post(
        "/api/agent/resume-draft/pdf", json={"model": "gpt-999"}, headers=headers
    )
    assert res.status_code == 422


def test_github_link_response_backward_compat_without_repos() -> None:
    """旧形式キャッシュ JSON（repos 無し）が GitHubLinkResponse として検証できる。"""
    legacy = {
        "username": "octo",
        "repos_analyzed": 3,
        "unique_skills": 2,
        "analyzed_at": "2025-01-01T00:00:00",
        "languages": {"Python": 100},
    }
    parsed = GitHubLinkResponse.model_validate(legacy)
    assert parsed.repos == []
