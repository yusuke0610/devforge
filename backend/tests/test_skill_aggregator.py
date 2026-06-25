"""スキル集計のテスト（ADR-0016 D1・D8）。"""

from app.services.intelligence.skills import (
    PackageDeclaration,
    RepoSkillInput,
    aggregate_skills,
)
from app.services.intelligence.skills.types import (
    SKILL_KIND_LANGUAGE,
    SKILL_KIND_PACKAGE,
)


def _repo(full_name="testuser/repo", languages=None, declarations=None) -> RepoSkillInput:
    return RepoSkillInput(
        full_name=full_name,
        url=f"https://github.com/{full_name}",
        languages=languages or {},
        package_declarations=declarations or [],
    )


def _by_name(skills) -> dict:
    return {s.canonical_name: s for s in skills}


def test_language_confidence_is_byte_share() -> None:
    """言語の confidence はリポ内バイト比率になり、除外言語は分母には残る。"""
    skills = aggregate_skills(
        [_repo(languages={"Python": 8000, "HTML": 2000})]
    )
    by_name = _by_name(skills)
    assert "HTML" not in by_name  # 除外
    python = by_name["Python"]
    assert python.kind == SKILL_KIND_LANGUAGE
    assert python.ecosystem == ""
    assert len(python.evidence) == 1
    assert python.evidence[0].confidence == 0.8
    assert python.evidence[0].language_bytes == 8000
    assert python.evidence[0].signal_source == "language_bytes"


def test_package_kinds_get_confidence() -> None:
    """direct と dev で confidence が変わること。"""
    skills = aggregate_skills(
        [
            _repo(
                declarations=[
                    PackageDeclaration("npm", "react", "direct"),
                    PackageDeclaration("npm", "jest", "dev"),
                ]
            )
        ]
    )
    by_name = _by_name(skills)
    assert by_name["react"].kind == SKILL_KIND_PACKAGE
    assert by_name["react"].ecosystem == "npm"
    assert by_name["react"].evidence[0].confidence == 0.6
    assert by_name["react"].evidence[0].dependency_kind == "direct"
    assert by_name["jest"].evidence[0].confidence == 0.3


def test_same_package_multiple_kinds_keeps_strongest() -> None:
    """同一リポで direct と dev の両方に出たら direct を採用すること（D7）。"""
    skills = aggregate_skills(
        [
            _repo(
                declarations=[
                    PackageDeclaration("npm", "typescript", "dev"),
                    PackageDeclaration("npm", "typescript", "direct"),
                ]
            )
        ]
    )
    ts = _by_name(skills)["typescript"]
    assert len(ts.evidence) == 1
    assert ts.evidence[0].dependency_kind == "direct"


def test_skill_deduped_across_repos_with_multiple_evidence() -> None:
    """複数リポに跨る同一スキルは 1 件に畳まれ、evidence が積み上がること（D8 保持）。"""
    skills = aggregate_skills(
        [
            _repo(full_name="u/a", languages={"Go": 1000}),
            _repo(full_name="u/b", languages={"Go": 4000}),
        ]
    )
    go = _by_name(skills)["Go"]
    assert len(go.evidence) == 2
    repos = {e.repo_full_name for e in go.evidence}
    assert repos == {"u/a", "u/b"}


def test_empty_repo_yields_no_skills() -> None:
    assert aggregate_skills([_repo()]) == []
