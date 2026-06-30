"""
Unit tests for the career intelligence services.

Tests cover deterministic modules only (no GitHub API calls).
"""

from app.services.intelligence.github_collector import RepoData
from app.services.intelligence.pipeline import (
    IntelligenceResult,
    aggregate_intelligence,
)
from app.services.intelligence.response_mapper import map_pipeline_result
from app.services.intelligence.skills import DetectedSkill

from conftest import auth_header

# ── Test Fixtures ───────────────────────────────────────────────────────


def _make_repo(
    name="my-repo",
    languages=None,
    topics=None,
    description="",
    created_at="2022-01-01T00:00:00Z",
    pushed_at="2023-06-01T00:00:00Z",
):
    return RepoData(
        name=name,
        owner="testuser",
        description=description,
        languages=languages or {},
        topics=topics or [],
        created_at=created_at,
        pushed_at=pushed_at,
        fork=False,
        stargazers_count=0,
        default_branch="main",
    )


def _make_skill(kind: str, canonical_name: str, ecosystem: str = "") -> DetectedSkill:
    """件数集計用の最小 DetectedSkill（evidence は本テストでは不問）。"""
    return DetectedSkill(
        kind=kind,
        canonical_name=canonical_name,
        ecosystem=ecosystem,
        parent=None,
        display_name=None,
    )


# ── Intelligence Endpoint Tests ────────────────────────────────────────


def test_analyze_requires_github_user(client) -> None:
    """通常ユーザー（非 GitHub）で analyze を呼ぶと 403 になること。"""
    headers = auth_header(client, "normal_analyze")
    resp = client.post(
        "/api/github-link/run",
        json={"include_forks": False},
        headers=headers,
    )
    assert resp.status_code == 403


# ── Response Mapper Tests ──────────────────────────────────────────────


def test_map_pipeline_result_includes_languages() -> None:
    """languages フィールドが正しくマッピングされること。"""
    result = IntelligenceResult(
        username="testuser",
        repos_analyzed=3,
        unique_skills=5,
        analyzed_at="2024-01-01T00:00:00",
        languages={"Python": 50000, "TypeScript": 30000},
    )
    response = map_pipeline_result(result)
    assert response.languages == {"Python": 50000, "TypeScript": 30000}
    assert response.username == "testuser"
    assert response.repos_analyzed == 3
    # 撤去したフィールドはレスポンス schema に存在しない
    assert not hasattr(response, "detected_frameworks")
    assert response.contribution_calendars == []


# ── aggregate_intelligence Tests（ADR-0016: 新基盤の検出スキルから集計）──────


def test_aggregate_intelligence_aggregates_languages() -> None:
    """複数リポジトリの言語バイト数が横断合算されること。"""
    repos = [
        _make_repo(name="repo-a", languages={"Python": 10000, "JavaScript": 5000}),
        _make_repo(name="repo-b", languages={"Python": 20000, "Go": 8000}),
    ]
    result = aggregate_intelligence("testuser", repos, detected_skills=[])

    assert result.languages["Python"] == 30000
    assert result.languages["JavaScript"] == 5000
    assert result.languages["Go"] == 8000
    assert result.repos_analyzed == 2


def test_aggregate_intelligence_unique_skills_counts_languages_only() -> None:
    """unique_skills が言語スキル（kind=language）の件数のみになり、package は除外されること。"""
    repos = [_make_repo(languages={"Python": 10000})]
    detected = [
        _make_skill("language", "Python"),
        _make_skill("language", "Go"),
        # package は dashboard の unique_skills 件数に含めない
        _make_skill("package", "fastapi", ecosystem="pypi"),
        _make_skill("package", "react", ecosystem="npm"),
    ]
    result = aggregate_intelligence("testuser", repos, detected)

    assert result.unique_skills == 2
    assert result.repos_analyzed == 1


def test_aggregate_intelligence_empty() -> None:
    """リポジトリ 0 件・スキル 0 件で空サマリになること。"""
    result = aggregate_intelligence("emptyuser", repos=[], detected_skills=[])

    assert result.repos_analyzed == 0
    assert result.unique_skills == 0
    assert result.languages == {}
