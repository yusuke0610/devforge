"""経歴書ドラフトのルールベースマッピング（mapper / context）の単体テスト（ADR-0018）。

mapper は純関数として DraftSource を直接組み立てて検証する。
context（スキル証跡の反転・連携キャッシュの検証）は実 SQLite セッションで検証する
（DB モック禁止 / .claude/rules/backend/test.md）。
"""

from datetime import date

import pytest
from app.models import GitHubLinkCache, User
from app.models.skill import GitHubSkill, GitHubSkillEvidence
from app.schemas.github_link import AnalyzedRepoSummary
from app.schemas.resume import TechnologyStackItem
from app.services.agent.resume_draft.context import (
    DraftSource,
    RepoTechnology,
    ResumeDraftNoRepositoriesError,
    ResumeDraftSourceUnavailableError,
    build_draft_source,
)
from app.services.agent.resume_draft.mapper import (
    PLACEHOLDER_COMPANY,
    PROJECT_LIMIT,
    STACK_LIMIT_PER_PROJECT,
    build_skeleton,
    select_repos,
)

_TODAY = date(2026, 7, 1)


def _repo(full_name: str, *, description: str = "", created: str = "2023-01-15T00:00:00Z",
          pushed: str = "2026-06-01T00:00:00Z") -> AnalyzedRepoSummary:
    """テスト用のリポジトリサマリを生成する。"""
    return AnalyzedRepoSummary(
        full_name=full_name, description=description, created_at=created, pushed_at=pushed
    )


def _source(repos: list, technologies: dict | None = None) -> DraftSource:
    """テスト用の DraftSource を生成する。"""
    return DraftSource(
        username="octocat",
        email="octo@example.com",
        repos=repos,
        repo_technologies=technologies or {},
    )


# ---------------------------------------------------------------------------
# select_repos: リポジトリ選定の決定論
# ---------------------------------------------------------------------------


def test_select_repos_orders_by_pushed_at_desc() -> None:
    """第 1 キーは最終 push 日時の降順。"""
    source = _source(
        [
            _repo("o/old", pushed="2024-01-01T00:00:00Z"),
            _repo("o/new", pushed="2026-06-01T00:00:00Z"),
            _repo("o/mid", pushed="2025-06-01T00:00:00Z"),
        ]
    )
    assert [r.full_name for r in select_repos(source)] == ["o/new", "o/mid", "o/old"]


def test_select_repos_tiebreaks_by_language_bytes_then_name() -> None:
    """push 日時が同じなら言語バイト合計の降順、それも同じなら名前の辞書順。"""
    pushed = "2026-06-01T00:00:00Z"
    source = _source(
        [_repo("o/small", pushed=pushed), _repo("o/big", pushed=pushed),
         _repo("o/b-zero", pushed=pushed), _repo("o/a-zero", pushed=pushed)],
        technologies={
            "o/small": [RepoTechnology("language", "Python", 0.9, language_bytes=100)],
            "o/big": [RepoTechnology("language", "Python", 0.9, language_bytes=9000)],
        },
    )
    assert [r.full_name for r in select_repos(source)] == [
        "o/big", "o/small", "o/a-zero", "o/b-zero",
    ]


def test_select_repos_caps_at_project_limit() -> None:
    """上限件数（PROJECT_LIMIT）で打ち切る。"""
    repos = [_repo(f"o/repo-{i}", pushed=f"2026-01-{i + 1:02d}T00:00:00Z") for i in range(8)]
    selected = select_repos(_source(repos))
    assert len(selected) == PROJECT_LIMIT
    # 直近 push 順に上位が選ばれている
    assert selected[0].full_name == "o/repo-7"


# ---------------------------------------------------------------------------
# build_skeleton: 骨格 payload の構築
# ---------------------------------------------------------------------------


def test_build_skeleton_top_level_and_placeholder_experience() -> None:
    """トップレベルとプレースホルダ職歴（個人開発）が契約どおり組み立てられる。"""
    source = _source(
        [
            _repo("o/first", created="2022-03-10T00:00:00Z"),
            _repo("o/second", created="2021-11-05T00:00:00Z"),
        ]
    )
    selected = select_repos(source)
    payload = build_skeleton(source, selected, today=_TODAY)

    assert payload["full_name"] == "octocat"
    assert payload["email"] == "octo@example.com"
    assert payload["github_url"] == "https://github.com/octocat"
    assert payload["career_summary"] == ""
    assert payload["self_pr"] == ""
    assert payload["qualifications"] == []

    (experience,) = payload["experiences"]
    assert experience["company"] == PLACEHOLDER_COMPANY
    assert experience["is_it_company"] is True
    assert experience["is_current"] is True
    assert experience["end_date"] == ""
    # 選定リポの最古 created_at（YYYY-MM）を職歴の開始にする
    assert experience["start_date"] == "2021-11"
    (client,) = experience["clients"]
    assert len(client["projects"]) == 2


def test_build_skeleton_project_period_current_boundary() -> None:
    """最終 push が 90 日以内なら参画中（end は空文字契約）、超えたら期間を閉じる。"""
    source = _source(
        [
            _repo("o/active", created="2024-01-01T00:00:00Z", pushed="2026-04-05T00:00:00Z"),
            _repo("o/stale", created="2024-01-01T00:00:00Z", pushed="2026-03-01T00:00:00Z"),
        ]
    )
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    projects = {p["name"]: p for p in payload["experiences"][0]["clients"][0]["projects"]}

    active_period = projects["active"]["periods"][0]
    assert active_period == {"start_date": "2024-01", "end_date": "", "is_current": True}

    stale_period = projects["stale"]["periods"][0]
    assert stale_period == {"start_date": "2024-01", "end_date": "2026-03", "is_current": False}


def test_build_skeleton_skips_period_without_created_at() -> None:
    """created_at が空のリポは期間を出さない（不正な期間を捏造しない）。"""
    source = _source([_repo("o/no-date", created="", pushed="")])
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    (project,) = payload["experiences"][0]["clients"][0]["projects"]
    assert project["periods"] == []
    # 職歴の開始も空になる
    assert payload["experiences"][0]["start_date"] == ""


def test_build_skeleton_description_falls_back_to_repo_description() -> None:
    """プロジェクト description は LLM マージ前のフォールバックとして repo description を持つ。"""
    source = _source([_repo("o/app", description="タスク管理アプリ")])
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    (project,) = payload["experiences"][0]["clients"][0]["projects"]
    assert project["description"] == "タスク管理アプリ"
    assert project["team"] == {"total": "1", "members": [{"role": "開発", "count": 1}]}
    assert project["phases"] == []


def test_build_skeleton_stacks_ordered_and_capped() -> None:
    """技術スタックはカテゴリ順（言語→FW→IaC）・量的シグナル降順で上限件数に絞る。"""
    technologies = [
        RepoTechnology("iac", "terraform-provider-aws", 0.9),
        RepoTechnology("framework", "fastapi", 0.9),
        RepoTechnology("language", "Python", 0.9, language_bytes=5000),
        RepoTechnology("language", "TypeScript", 0.9, language_bytes=9000),
    ] + [RepoTechnology("framework", f"lib-{i}", 0.5 - i * 0.01) for i in range(6)]
    source = _source([_repo("o/app")], technologies={"o/app": technologies})
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    (project,) = payload["experiences"][0]["clients"][0]["projects"]

    stacks = project["technology_stacks"]
    assert len(stacks) == STACK_LIMIT_PER_PROJECT
    # 言語がバイト数降順で先頭に並ぶ
    assert stacks[0] == {"category": "language", "name": "TypeScript"}
    assert stacks[1] == {"category": "language", "name": "Python"}
    # framework は confidence 降順（fastapi 0.9 が先頭）
    assert stacks[2] == {"category": "framework", "name": "fastapi"}
    # 各カテゴリが保存契約（schemas/resume.py の Literal）に収まる
    for stack in stacks:
        TechnologyStackItem.model_validate(stack)


# ---------------------------------------------------------------------------
# context: 連携キャッシュの検証とスキル証跡の反転（実 SQLite）
# ---------------------------------------------------------------------------


def _create_user(db_session) -> User:
    """テスト用ユーザーを作成して返す。"""
    user = User(username="octocat", email="octo@example.com")
    db_session.add(user)
    db_session.commit()
    return user


def _cache_result(repos: list[dict] | None) -> dict:
    """連携キャッシュの result JSON を生成する（repos=None で旧形式を再現）。"""
    result: dict = {
        "username": "octocat",
        "repos_analyzed": 1,
        "unique_skills": 1,
        "analyzed_at": "2026-06-01T00:00:00",
        "languages": {"Python": 1000},
    }
    if repos is not None:
        result["repos"] = repos
    return result


def _add_skill(db_session, user_id: str, *, kind: str, name: str, evidence: list[dict]) -> None:
    """スキル + 証跡を直接投入する。"""
    skill = GitHubSkill(user_id=user_id, kind=kind, canonical_name=name)
    skill.evidence = [GitHubSkillEvidence(**ev) for ev in evidence]
    db_session.add(skill)
    db_session.commit()


def test_build_draft_source_requires_completed_cache(db_session) -> None:
    """キャッシュ無し・未完了はドラフト入力を組み立てられない。"""
    user = _create_user(db_session)
    with pytest.raises(ResumeDraftSourceUnavailableError):
        build_draft_source(db_session, user)

    db_session.add(GitHubLinkCache(user_id=user.id, status="processing", result=None))
    db_session.commit()
    with pytest.raises(ResumeDraftSourceUnavailableError):
        build_draft_source(db_session, user)


def test_build_draft_source_rejects_legacy_cache_without_repos(db_session) -> None:
    """ADR-0018 以前の旧形式キャッシュ（repos キー無し）は再連携が必要。"""
    user = _create_user(db_session)
    db_session.add(
        GitHubLinkCache(user_id=user.id, status="completed", result=_cache_result(repos=None))
    )
    db_session.commit()
    with pytest.raises(ResumeDraftSourceUnavailableError):
        build_draft_source(db_session, user)


def test_build_draft_source_rejects_empty_repos_as_no_repositories(db_session) -> None:
    """新形式で repos が空リスト（分析対象 0 件）は旧形式と区別され、専用例外になる。"""
    user = _create_user(db_session)
    db_session.add(
        GitHubLinkCache(user_id=user.id, status="completed", result=_cache_result(repos=[]))
    )
    db_session.commit()
    # 0 件は旧形式（再連携で回復）ではなく NoRepositories（リポジトリ追加が必要）
    with pytest.raises(ResumeDraftNoRepositoriesError):
        build_draft_source(db_session, user)


def test_build_draft_source_inverts_skill_evidence(db_session) -> None:
    """スキル証跡が「リポ → 技術」に反転され、採用基準どおりフィルタされる。"""
    user = _create_user(db_session)
    repo_summary = {
        "full_name": "octocat/app",
        "description": "アプリ",
        "created_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2026-06-01T00:00:00Z",
    }
    db_session.add(
        GitHubLinkCache(
            user_id=user.id, status="completed", result=_cache_result(repos=[repo_summary])
        )
    )
    db_session.commit()

    _add_skill(
        db_session, user.id, kind="language", name="Python",
        evidence=[{
            "repo_full_name": "octocat/app", "signal_source": "language_bytes",
            "confidence": 0.9, "language_bytes": 1234,
        }],
    )
    # direct 宣言 + 実 import の二重証跡 → confidence の大きい方に畳まれる
    _add_skill(
        db_session, user.id, kind="package", name="fastapi",
        evidence=[
            {"repo_full_name": "octocat/app", "signal_source": "manifest_declared",
             "confidence": 0.6, "dependency_kind": "direct"},
            {"repo_full_name": "octocat/app", "signal_source": "actual_import",
             "confidence": 0.8, "dependency_kind": "direct"},
        ],
    )
    # 間接依存（direct でも actual_import でもない）→ 採用しない
    _add_skill(
        db_session, user.id, kind="package", name="urllib3",
        evidence=[{
            "repo_full_name": "octocat/app", "signal_source": "manifest_declared",
            "confidence": 0.3, "dependency_kind": "indirect",
        }],
    )
    _add_skill(
        db_session, user.id, kind="infra", name="aws",
        evidence=[{
            "repo_full_name": "octocat/app", "signal_source": "infra_declared",
            "confidence": 0.7,
        }],
    )

    source = build_draft_source(db_session, user)
    assert source.username == "octocat"
    assert [r.full_name for r in source.repos] == ["octocat/app"]

    technologies = {
        (t.category, t.name): t for t in source.repo_technologies["octocat/app"]
    }
    assert set(technologies) == {
        ("language", "Python"), ("framework", "fastapi"), ("iac", "aws"),
    }
    assert technologies[("language", "Python")].language_bytes == 1234
    assert technologies[("framework", "fastapi")].confidence == 0.8
