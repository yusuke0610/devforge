"""run_resume_draft_task（経歴書ドラフト生成タスク本体 / ADR-0018 非同期化）の単体テスト。

LLM のみモックし、連携データ読み取り・ルールベースマッピング・PDF レンダリング・課金配線は
実コードを通す（DB は実 SQLite セッション）。課金順序の不変条件を固定する:
  - 成功: completed + result 保存 + 使用ログ記録（無料モデルは credit_cost=0）。
  - パース失敗: 消費済みトークンを課金してから NonRetryableError（worker が dead_letter 化）。
  - PDF 生成失敗: 課金せず NonRetryableError（使用ログを残さない）。
"""

import json

import pytest
from app.models import GitHubLinkCache, ResumeDraftCache
from app.models.billing import AgentUsageLog
from app.models.skill import GitHubSkill, GitHubSkillEvidence
from app.repositories import UserRepository
from app.services.agent.llm.base import LLMClient, LLMResult
from app.services.agent.resume_draft import draft_service, run_task
from app.services.agent.resume_draft.run_task import run_resume_draft_task
from app.services.tasks.exceptions import NonRetryableError
from sqlalchemy.orm import Session

from ._helpers import run_sync as _run


class _FakeLLM(LLMClient):
    """固定応答を返すテスト用 LLM クライアント。"""

    def __init__(self, response: str, input_tokens: int = 100, output_tokens: int = 200):
        self._response = response
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    async def generate(self, system_prompt, messages, output_schema, model_id) -> LLMResult:
        return LLMResult(
            text=self._response,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
        )


def _draft_response() -> str:
    """契約に沿ったドラフト応答 JSON。"""
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


def _seed(db: Session, username: str = "draft-user", *, repos: bool = True):
    """ユーザー + 連携キャッシュ（+ スキル証跡）+ ドラフトキャッシュ(pending) を投入する。"""
    user = UserRepository(db).create(username, email=f"{username}@test.com")
    result = {
        "username": username,
        "repos_analyzed": 1 if repos else 0,
        "unique_skills": 1 if repos else 0,
        "analyzed_at": "2026-06-01T00:00:00",
        "languages": {"Python": 1000} if repos else {},
        "repos": (
            [
                {
                    "full_name": "octo/app",
                    "description": "タスク管理アプリ",
                    "created_at": "2024-01-01T00:00:00Z",
                    "pushed_at": "2026-06-01T00:00:00Z",
                }
            ]
            if repos
            else []
        ),
    }
    db.add(GitHubLinkCache(user_id=user.id, status="completed", result=result))
    if repos:
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
    db.add(ResumeDraftCache(user_id=user.id, status="pending"))
    db.commit()
    return user


def test_task_completes_and_records_usage(db_session, session_factory, monkeypatch):
    """成功: status=completed + result 保存 + 使用ログ記録（無料モデルは credit_cost=0）。"""
    user = _seed(db_session)
    monkeypatch.setattr(draft_service, "get_llm_client", lambda provider: _FakeLLM(_draft_response()))

    _run(run_resume_draft_task(session_factory, {"user_id": user.id, "model": "haiku"}))

    db_session.expire_all()
    draft = db_session.query(ResumeDraftCache).filter_by(user_id=user.id).one()
    assert draft.status == "completed"
    assert draft.result is not None
    assert draft.result["career_summary"] == "生成された職務要約。"
    assert draft.completed_at is not None

    (log,) = db_session.query(AgentUsageLog).all()
    assert log.model_alias == "haiku"
    assert log.input_tokens == 100
    assert log.output_tokens == 200
    assert log.credit_cost == 0


def test_task_parse_failure_charges_and_raises(db_session, session_factory, monkeypatch):
    """パース失敗: 消費済みトークン（2 コール合算）を課金し NonRetryableError を送出する。"""
    user = _seed(db_session)
    monkeypatch.setattr(
        draft_service, "get_llm_client", lambda provider: _FakeLLM("JSON ではない応答")
    )

    with pytest.raises(NonRetryableError):
        _run(run_resume_draft_task(session_factory, {"user_id": user.id, "model": "haiku"}))

    db_session.expire_all()
    (log,) = db_session.query(AgentUsageLog).all()
    assert log.input_tokens == 200
    assert log.output_tokens == 400


def test_task_pdf_failure_not_charged(db_session, session_factory, monkeypatch):
    """PDF 生成失敗: 課金せず NonRetryableError を送出する（使用ログを残さない）。"""
    user = _seed(db_session)
    monkeypatch.setattr(draft_service, "get_llm_client", lambda provider: _FakeLLM(_draft_response()))

    def _fail_pdf(_payload):
        raise RuntimeError("PDF 生成失敗")

    monkeypatch.setattr(run_task, "build_resume_pdf", _fail_pdf)

    with pytest.raises(NonRetryableError):
        _run(run_resume_draft_task(session_factory, {"user_id": user.id, "model": "haiku"}))

    db_session.expire_all()
    assert db_session.query(AgentUsageLog).count() == 0


def test_task_source_unavailable_raises_non_retryable(db_session, session_factory):
    """分析対象リポジトリ 0 件は回復しないため NonRetryableError。"""
    user = _seed(db_session, "no-repos-user", repos=False)
    with pytest.raises(NonRetryableError):
        _run(run_resume_draft_task(session_factory, {"user_id": user.id, "model": "haiku"}))


def test_task_missing_cache_raises_non_retryable(session_factory):
    """ドラフトキャッシュが無い場合は NonRetryableError（worker が dead_letter 化）。"""
    with pytest.raises(NonRetryableError):
        _run(
            run_resume_draft_task(
                session_factory, {"user_id": "nonexistent-user-id", "model": "haiku"}
            )
        )
