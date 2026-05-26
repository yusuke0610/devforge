"""
Unit tests for the career intelligence services.

Tests cover deterministic modules only (no GitHub API calls).
"""

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.intelligence.github.repo_analyzer import parse_go_mod, parse_pom_xml
from app.services.intelligence.github_collector import RepoData
from app.services.intelligence.pipeline import IntelligenceResult, run_pipeline
from app.services.intelligence.response_mapper import map_pipeline_result
from app.services.intelligence.skill_extractor import extract_skills

from conftest import auth_header

# ── Test Fixtures ───────────────────────────────────────────────────────


def _make_repo(
    name="my-repo",
    languages=None,
    topics=None,
    description="",
    created_at="2022-01-01T00:00:00Z",
    pushed_at="2023-06-01T00:00:00Z",
    dependencies=None,
    root_files=None,
    detected_frameworks=None,
    detected_devtools=None,
    detected_infras=None,
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
        dependencies=dependencies or [],
        root_files=root_files or [],
        detected_frameworks=detected_frameworks or [],
        detected_devtools=detected_devtools or [],
        detected_infras=detected_infras or [],
    )


SAMPLE_REPOS = [
    _make_repo(
        name="web-api",
        languages={"Python": 50000, "Dockerfile": 500},
        topics=["fastapi", "docker", "postgresql"],
        description="FastAPI backend with PostgreSQL",
        created_at="2021-03-01T00:00:00Z",
        pushed_at="2024-01-15T00:00:00Z",
    ),
    _make_repo(
        name="infra",
        languages={"HCL": 30000, "Shell": 2000},
        topics=["terraform", "gcp", "kubernetes"],
        description="GCP infrastructure with Terraform",
        created_at="2023-01-01T00:00:00Z",
        pushed_at="2024-06-01T00:00:00Z",
    ),
    _make_repo(
        name="frontend",
        languages={"TypeScript": 40000, "JavaScript": 5000},
        topics=["react", "nextjs"],
        description="React frontend",
        created_at="2022-06-01T00:00:00Z",
        pushed_at="2023-12-01T00:00:00Z",
    ),
    _make_repo(
        name="old-java",
        languages={"Java": 80000},
        topics=["spring-boot"],
        description="Legacy Spring Boot service",
        created_at="2019-01-01T00:00:00Z",
        pushed_at="2020-06-01T00:00:00Z",
    ),
    _make_repo(
        name="scripts",
        languages={"Python": 3000},
        topics=[],
        description="Utility scripts",
        created_at="2020-01-01T00:00:00Z",
        pushed_at="2020-12-01T00:00:00Z",
    ),
]


# ── Skill Extractor ─────────────────────────────────────────────────────


class TestSkillExtractor:
    def test_extracts_from_languages(self):
        repos = [_make_repo(languages={"Python": 10000, "Go": 5000})]
        result = extract_skills(repos)
        names = {s.skill_name for s in result.skills}
        assert "Python" in names
        assert "Go" in names

    def test_extracts_from_topics(self):
        repos = [_make_repo(topics=["react", "docker", "postgresql"])]
        result = extract_skills(repos)
        names = {s.skill_name for s in result.skills}
        assert "React" in names
        assert "Docker" in names
        assert "PostgreSQL" in names

    def test_extracts_from_description(self):
        repos = [_make_repo(description="Built with FastAPI and Redis")]
        result = extract_skills(repos)
        names = {s.skill_name for s in result.skills}
        assert "FastAPI" in names
        assert "Redis" in names

    def test_deduplicates_within_repo(self):
        """Same skill from language + topic should appear once per repo."""
        repos = [
            _make_repo(
                languages={"Python": 10000},
                topics=["fastapi"],
                description="A FastAPI project",
            )
        ]
        result = extract_skills(repos)
        python_count = sum(
            1
            for s in result.skills
            if s.skill_name == "Python" and s.repo_name == "my-repo"
        )
        assert python_count == 1

    def test_hcl_maps_to_terraform(self):
        repos = [_make_repo(languages={"HCL": 5000})]
        result = extract_skills(repos)
        names = {s.skill_name for s in result.skills}
        assert "Terraform" in names

    def test_empty_repos(self):
        result = extract_skills([])
        assert result.skills == []
        assert result.repos_analyzed == 0

    def test_unique_skills_count(self):
        result = extract_skills(SAMPLE_REPOS)
        assert len(result.unique_skills) > 5
        assert result.repos_analyzed == 5

    def test_source_tracking(self):
        repos = [
            _make_repo(
                languages={"Python": 10000},
                topics=["docker"],
            )
        ]
        result = extract_skills(repos)
        sources = {s.source for s in result.skills}
        assert "language" in sources
        assert "topic" in sources

    def test_extracts_from_dependencies(self):
        repos = [
            _make_repo(
                dependencies=["fastapi", "sqlalchemy", "uvicorn"],
            )
        ]
        result = extract_skills(repos)
        names = {s.skill_name for s in result.skills}
        assert "FastAPI" in names
        assert "SQLAlchemy" in names

    def test_extracts_from_detected_devtools_and_infras(self):
        repos = [
            _make_repo(
                detected_devtools=["Docker", "GitHub Actions"],
                detected_infras=["Terraform"],
            )
        ]
        result = extract_skills(repos)
        names = {s.skill_name for s in result.skills}
        assert "Docker" in names
        assert "GitHub Actions" in names
        assert "Terraform" in names

    def test_dependency_source_label(self):
        repos = [_make_repo(dependencies=["fastapi"])]
        result = extract_skills(repos)
        sources = {s.source for s in result.skills}
        assert "dependency" in sources

    def test_root_file_source_label(self):
        repos = [_make_repo(detected_devtools=["Docker"])]
        result = extract_skills(repos)
        sources = {s.source for s in result.skills}
        assert "root_file" in sources

    def test_dedup_dependency_and_topic(self):
        """Same skill from topic + dependency should appear once."""
        repos = [
            _make_repo(
                topics=["fastapi"],
                dependencies=["fastapi"],
            )
        ]
        result = extract_skills(repos)
        fastapi_count = sum(1 for s in result.skills if s.skill_name == "FastAPI")
        assert fastapi_count == 1

    def test_dedup_root_file_and_language(self):
        """Docker from language + root_file should appear once."""
        repos = [
            _make_repo(
                languages={"Dockerfile": 500},
                detected_devtools=["Docker"],
            )
        ]
        result = extract_skills(repos)
        docker_count = sum(1 for s in result.skills if s.skill_name == "Docker")
        assert docker_count == 1

    def test_full_repo_with_all_sources(self):
        """A realistic repo should produce rich skill set."""
        repos = [
            _make_repo(
                name="fullstack-app",
                languages={"Python": 50000, "Dockerfile": 500},
                topics=["fastapi", "postgresql"],
                description="Backend API",
                dependencies=["fastapi", "sqlalchemy", "boto3"],
                root_files=["Dockerfile", ".github", "terraform"],
                detected_devtools=["Docker", "GitHub Actions"],
                detected_infras=["Terraform"],
            )
        ]
        result = extract_skills(repos)
        names = {s.skill_name for s in result.skills}
        assert "Python" in names
        assert "FastAPI" in names
        assert "PostgreSQL" in names
        assert "Docker" in names
        assert "GitHub Actions" in names
        assert "Terraform" in names
        assert "SQLAlchemy" in names
        assert "AWS" in names  # from boto3 dependency


# ── Dependency Parsing（github_collector 経由でのみ確認すべき pom.xml / go.mod のみ）─────
# 一般的な requirements.txt / package.json / root file 検出は test_repo_analyzer.py で網羅。


class TestDependencyParsing:
    def test_parse_pom_xml(self):

        content = (
            "<project><dependencies><dependency>"
            "<artifactId>spring-boot-starter-web</artifactId>"
            "</dependency></dependencies></project>"
        )
        result = parse_pom_xml(content)
        assert "spring-boot-starter-web" in result

    def test_parse_go_mod(self):

        content = (
            "module example.com/app\n\nrequire (\n"
            "\tgithub.com/gin-gonic/gin v1.9\n)\n"
        )
        result = parse_go_mod(content)
        assert "github.com/gin-gonic/gin" in result


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


# ── Pipeline Tests ──────────────────────────────────────────────────────


def _make_pipeline_repo(name: str, languages: dict | None = None) -> RepoData:
    """パイプラインテスト用のリポジトリデータを生成するヘルパー。"""
    return RepoData(
        name=name,
        owner="testuser",
        description="",
        languages=languages or {},
        topics=[],
        created_at="2024-01-01T00:00:00Z",
        pushed_at="2024-06-01T00:00:00Z",
        fork=False,
        stargazers_count=0,
        default_branch="main",
        dependencies=[],
        root_files=[],
        detected_frameworks=[],
        detected_devtools=[],
        detected_infras=[],
    )


def test_run_pipeline_aggregates_languages() -> None:
    """複数リポジトリの言語バイト数が正しく集計されること。"""
    repos = [
        _make_pipeline_repo("repo-a", {"Python": 10000, "JavaScript": 5000}),
        _make_pipeline_repo("repo-b", {"Python": 20000, "Go": 8000}),
    ]

    with patch(
        "app.services.intelligence.pipeline.collect_repos",
        new_callable=AsyncMock,
        return_value=repos,
    ):
        result = asyncio.get_event_loop().run_until_complete(run_pipeline(username="testuser"))

    assert result.languages["Python"] == 30000
    assert result.languages["JavaScript"] == 5000
    assert result.languages["Go"] == 8000


def test_run_pipeline_empty_repos() -> None:
    """リポジトリ 0 件で正常終了すること。"""
    with patch(
        "app.services.intelligence.pipeline.collect_repos",
        new_callable=AsyncMock,
        return_value=[],
    ):
        result = asyncio.get_event_loop().run_until_complete(run_pipeline(username="emptyuser"))

    assert result.repos_analyzed == 0
    assert result.unique_skills == 0
    assert result.languages == {}
