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
from app.schemas.agent import RESUME_DRAFT_SELECTION_LIMIT
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
                # ADR-0026 決定 4 の選定シグナル。欠けると旧形式扱いで 409 になる
                "topics": ["python"],
                "language_bytes_total": 1000,
                "direct_dependency_count": 2,
                "ecosystem_count": 1,
                "has_infra": False,
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


def _run_body(*, model: str = "haiku", repos: list[str] | None = None) -> dict:
    """生成リクエストの body を組み立てる（採用リポジトリ指定は必須 / ADR-0026 決定 2）。"""
    return {"model": model, "repo_full_names": repos if repos is not None else ["octo/app"]}


# ── candidates（GET /candidates）─────────────────────────────────────────


def test_resume_draft_candidates_returns_all_repositories(client: TestClient) -> None:
    """連携済みなら候補が全件返り、シグナルと選択状態を持つ。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)

    res = client.get("/api/agent/resume-draft/candidates", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["selection_limit"] == RESUME_DRAFT_SELECTION_LIMIT
    (candidate,) = body["candidates"]
    assert candidate["full_name"] == "octo/app"
    assert candidate["description"] == "タスク管理アプリ"
    # 継続期間 2 年超 + 学習用途 topics なし → デフォルト採用
    assert candidate["duration_days"] > 0
    assert candidate["implementation_volume"] > 0
    assert candidate["has_infra"] is False
    assert candidate["technology_stacks"] == [{"category": "language", "name": "Python"}]
    assert candidate["default_selected"] is True
    assert candidate["reasons"] == []


def test_resume_draft_candidates_keeps_noise_with_reasons(client: TestClient) -> None:
    """ノイズ判定されたリポジトリも候補から落とさず、理由付きで非選択にする。"""
    headers = auth_header(client, github_id=1)
    user = client._db_session.query(User).filter_by(username="testuser").one()
    client._db_session.add(
        GitHubLinkCache(
            user_id=user.id,
            status="completed",
            result={
                "username": "testuser",
                "repos_analyzed": 1,
                "unique_skills": 0,
                "analyzed_at": "2026-06-01T00:00:00",
                "languages": {},
                "repos": [
                    {
                        "full_name": "octo/tutorial",
                        "description": "写経",
                        "created_at": "2026-05-30T00:00:00Z",
                        "pushed_at": "2026-06-01T00:00:00Z",
                        "topics": ["tutorial"],
                        "language_bytes_total": 100,
                        "direct_dependency_count": 0,
                        "ecosystem_count": 0,
                        "has_infra": False,
                    }
                ],
            },
        )
    )
    client._db_session.commit()

    res = client.get("/api/agent/resume-draft/candidates", headers=headers)

    assert res.status_code == 200
    (candidate,) = res.json()["candidates"]
    assert candidate["full_name"] == "octo/tutorial"
    assert candidate["default_selected"] is False
    assert candidate["reasons"] == ["short_duration", "learning_topic"]


def test_resume_draft_candidates_requires_github_login(client: TestClient) -> None:
    """GitHub 未連携ユーザー（github_id 無し）は 403。"""
    headers = auth_header(client)
    res = client.get("/api/agent/resume-draft/candidates", headers=headers)
    assert res.status_code == 403


def test_resume_draft_candidates_conflict_without_link_cache(client: TestClient) -> None:
    """連携未実行は 409（GitHub 連携の実行を促す）。"""
    headers = auth_header(client, github_id=1)
    res = client.get("/api/agent/resume-draft/candidates", headers=headers)
    assert res.status_code == 409


# ── enqueue（POST /run）──────────────────────────────────────────────────


def test_resume_draft_run_enqueues(client: TestClient) -> None:
    """連携済みなら 202 を返し、キャッシュが pending へ遷移する。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)

    res = client.post("/api/agent/resume-draft/run", json=_run_body(), headers=headers)

    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    cache = client._db_session.query(ResumeDraftCache).filter_by(
        user_id=client._db_session.query(User).filter_by(username="testuser").one().id
    ).one()
    assert cache.status == "pending"


def test_resume_draft_run_requires_github_login(client: TestClient) -> None:
    """GitHub 未連携ユーザー（github_id 無し）は 403。"""
    headers = auth_header(client)
    res = client.post("/api/agent/resume-draft/run", json=_run_body(), headers=headers)
    assert res.status_code == 403


def test_resume_draft_run_conflict_without_link_cache(client: TestClient) -> None:
    """連携未実行は 409（GitHub 連携の実行を促す）。"""
    headers = auth_header(client, github_id=1)
    res = client.post("/api/agent/resume-draft/run", json=_run_body(), headers=headers)
    assert res.status_code == 409


def test_resume_draft_run_conflict_with_legacy_cache(client: TestClient) -> None:
    """repos キーを持たない旧形式キャッシュは 409（再連携を促す）。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session, legacy=True)
    res = client.post("/api/agent/resume-draft/run", json=_run_body(), headers=headers)
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

    res = client.post("/api/agent/resume-draft/run", json=_run_body(), headers=headers)
    assert res.status_code == 409
    assert "公開リポジトリ" in res.json()["message"]


def test_resume_draft_run_rejects_empty_selection(client: TestClient) -> None:
    """採用リポジトリ 0 件はスキーマ検証で 422（何も選ばずには生成しない）。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)
    res = client.post(
        "/api/agent/resume-draft/run", json=_run_body(repos=[]), headers=headers
    )
    assert res.status_code == 422


def test_resume_draft_run_rejects_selection_over_limit(client: TestClient) -> None:
    """上限（RESUME_DRAFT_SELECTION_LIMIT）を超える採用指定は 422。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)
    over_limit = [f"octo/repo-{i}" for i in range(RESUME_DRAFT_SELECTION_LIMIT + 1)]
    res = client.post(
        "/api/agent/resume-draft/run", json=_run_body(repos=over_limit), headers=headers
    )
    assert res.status_code == 422


def test_resume_draft_run_rejects_unknown_repository(client: TestClient) -> None:
    """連携データに無いリポジトリの指定は 422（捏造リポの混入を入口で止める）。"""
    headers = auth_header(client, github_id=1)
    _seed_link_data(client._db_session)
    res = client.post(
        "/api/agent/resume-draft/run", json=_run_body(repos=["octo/ghost"]), headers=headers
    )
    assert res.status_code == 422
    # キャッシュを作らずに弾く（生成タスクは起きない）
    assert client._db_session.query(ResumeDraftCache).count() == 0


def test_resume_draft_run_invalid_model_rejected(client: TestClient) -> None:
    """未知のモデルエイリアスはスキーマ検証で 422。"""
    headers = auth_header(client, github_id=1)
    res = client.post(
        "/api/agent/resume-draft/run", json=_run_body(model="gpt-999"), headers=headers
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


# ── payload 取得（GET /result / ADR-0025・#525）──────────────────────────


def test_resume_draft_result_success(client: TestClient) -> None:
    """完了済みキャッシュの payload が JSON で返る（フォーム注入用 / ADR-0025）。"""
    headers = auth_header(client, github_id=1)
    user = client._db_session.query(User).filter_by(username="testuser").one()
    client._db_session.add(
        ResumeDraftCache(user_id=user.id, status="completed", result=_draft_payload())
    )
    client._db_session.commit()

    res = client.get("/api/agent/resume-draft/result", headers=headers)

    assert res.status_code == 200
    body = res.json()
    assert body["full_name"] == "testuser"
    assert body["career_summary"] == "生成された職務要約。"
    assert body["self_pr"] == "生成された自己PR。"
    # 出力単位は project 明細のリスト（ADR-0026 決定 1）。experience は返さない
    assert "experiences" not in body
    assert [p["name"] for p in body["projects"]] == ["app"]
    # GitHub から得られない値は空のまま（プレースホルダを生成しない）
    assert body["projects"][0]["role"] == ""
    assert body["projects"][0]["phases"] == []
    assert body["projects"][0]["team"] == {"total": "", "members": []}


def test_resume_draft_result_not_ready(client: TestClient) -> None:
    """未生成（キャッシュ無し）の payload 取得は 409。"""
    headers = auth_header(client, github_id=1)
    res = client.get("/api/agent/resume-draft/result", headers=headers)
    assert res.status_code == 409


def test_resume_draft_result_requires_github_login(client: TestClient) -> None:
    """GitHub 未連携ユーザーの payload 取得は 403。"""
    headers = auth_header(client)
    res = client.get("/api/agent/resume-draft/result", headers=headers)
    assert res.status_code == 403


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
