"""経歴書ドラフト生成エンドポイント（非同期 / ADR-0018）の統合テスト。

``POST /api/agent/resume-draft/run``（enqueue）/ ``GET .../status``（ポーリング）/
``GET .../pdf``（ダウンロード）を実コードで通す（DB は実 SQLite セッション）。

``client`` fixture は ``execute_task`` を no-op に差し替えるため、本ファイルでは enqueue の
受付・状態遷移・認可・バリデーションと、完了済みキャッシュからのダウンロードを検証する。
生成タスク本体（LLM → PDF → 課金 → completed）の検証は
``tests/test_worker/test_resume_draft.py`` で行う。
"""

from datetime import date

from app.models import GitHubLinkCache, ResumeDraftCache, User
from app.schemas.github_link import AnalyzedRepoSummary, GitHubLinkResponse
from app.services.agent.resume_draft.context import DraftSource, RepoTechnology
from app.services.agent.resume_draft.mapper import build_skeleton, select_repos
from fastapi.testclient import TestClient

from conftest import auth_header


def _seed_link_data(db, username: str = "testuser", *, legacy: bool = False) -> None:
    """連携キャッシュ（+ スキル証跡）を投入する。legacy=True で repos 無しの旧形式。"""
    from app.models.skill import GitHubSkill, GitHubSkillEvidence

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


def _draft_payload() -> dict:
    """build_resume_pdf が受け取れる有効なドラフト payload を決定論的に組み立てる。"""
    source = DraftSource(
        username="testuser",
        email="testuser@example.com",
        repos=[
            AnalyzedRepoSummary(
                full_name="octo/app",
                description="タスク管理アプリ",
                created_at="2024-01-01T00:00:00Z",
                pushed_at="2026-06-01T00:00:00Z",
            )
        ],
        repo_technologies={
            "octo/app": [RepoTechnology(category="language", name="Python", confidence=0.9, language_bytes=1000)]
        },
    )
    selected = select_repos(source)
    payload = build_skeleton(source, selected, today=date(2026, 6, 15))
    payload["career_summary"] = "生成された職務要約。"
    payload["self_pr"] = "生成された自己PR。"
    return payload


# ── enqueue（POST /run）──────────────────────────────────────────────────


def test_resume_draft_run_enqueues(client: TestClient) -> None:
    """連携済みなら 202 を返し、キャッシュが pending へ遷移する。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)

    res = client.post("/api/agent/resume-draft/run", json={"model": "haiku"}, headers=headers)

    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    cache = client._db_session.query(ResumeDraftCache).filter_by(
        user_id=client._db_session.query(User).filter_by(username="testuser").one().id
    ).one()
    assert cache.status == "pending"


def test_resume_draft_run_requires_github_login(client: TestClient) -> None:
    """GitHub 未連携ユーザー（github_id 無し）は 403。"""
    headers = auth_header(client)
    res = client.post("/api/agent/resume-draft/run", json={"model": "haiku"}, headers=headers)
    assert res.status_code == 403


def test_resume_draft_run_conflict_without_link_cache(client: TestClient) -> None:
    """連携未実行は 409（GitHub 連携の実行を促す）。"""
    headers = auth_header(client, github_id=1)
    res = client.post("/api/agent/resume-draft/run", json={"model": "haiku"}, headers=headers)
    assert res.status_code == 409


def test_resume_draft_run_conflict_with_legacy_cache(client: TestClient) -> None:
    """repos キーを持たない旧形式キャッシュは 409（再連携を促す）。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session, legacy=True)
    res = client.post("/api/agent/resume-draft/run", json={"model": "haiku"}, headers=headers)
    assert res.status_code == 409


def test_resume_draft_run_conflict_with_zero_repositories(client: TestClient) -> None:
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

    res = client.post("/api/agent/resume-draft/run", json={"model": "haiku"}, headers=headers)
    assert res.status_code == 409
    assert "公開リポジトリ" in res.json()["message"]


def test_resume_draft_run_invalid_model_rejected(client: TestClient) -> None:
    """未知のモデルエイリアスはスキーマ検証で 422。"""
    headers = auth_header(client, github_id=1)
    res = client.post(
        "/api/agent/resume-draft/run", json={"model": "gpt-999"}, headers=headers
    )
    assert res.status_code == 422


# ── status（GET /status）────────────────────────────────────────────────


def test_resume_draft_status_defaults_completed_without_cache(client: TestClient) -> None:
    """キャッシュが無ければ completed（アイドル）を返す。"""
    headers = auth_header(client, github_id=1)
    res = client.get("/api/agent/resume-draft/status", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "completed"


def test_resume_draft_status_reports_dead_letter(client: TestClient) -> None:
    """dead_letter とエラーメッセージがステータスに反映される。"""
    headers = auth_header(client, github_id=1)
    user = client._db_session.query(User).filter_by(username="testuser").one()
    client._db_session.add(
        ResumeDraftCache(
            user_id=user.id, status="dead_letter", error_message="AI の応答取得に失敗しました。"
        )
    )
    client._db_session.commit()

    res = client.get("/api/agent/resume-draft/status", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "dead_letter"
    assert body["error_message"] == "AI の応答取得に失敗しました。"


# ── download（GET /pdf）─────────────────────────────────────────────────


def test_resume_draft_pdf_download_success(client: TestClient) -> None:
    """完了済みキャッシュの payload から PDF が再レンダリングされて返る。"""
    headers = auth_header(client, github_id=1)
    user = client._db_session.query(User).filter_by(username="testuser").one()
    client._db_session.add(
        ResumeDraftCache(user_id=user.id, status="completed", result=_draft_payload())
    )
    client._db_session.commit()

    res = client.get("/api/agent/resume-draft/pdf", headers=headers)

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")


def test_resume_draft_pdf_download_not_ready(client: TestClient) -> None:
    """未生成（キャッシュ無し）のダウンロードは 409。"""
    headers = auth_header(client, github_id=1)
    res = client.get("/api/agent/resume-draft/pdf", headers=headers)
    assert res.status_code == 409


def test_resume_draft_pdf_download_conflict_while_processing(client: TestClient) -> None:
    """生成中（processing・result 無し）のダウンロードは 409。"""
    headers = auth_header(client, github_id=1)
    user = client._db_session.query(User).filter_by(username="testuser").one()
    client._db_session.add(ResumeDraftCache(user_id=user.id, status="processing"))
    client._db_session.commit()

    res = client.get("/api/agent/resume-draft/pdf", headers=headers)
    assert res.status_code == 409


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
