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


def test_pypi_names_are_pep503_normalized() -> None:
    """pypi は大小文字・区切り差を畳んで同一スキルにすること（PEP 503）。"""
    skills = aggregate_skills(
        [
            _repo(
                full_name="u/a",
                declarations=[PackageDeclaration("pypi", "ruamel.yaml", "direct")],
            ),
            _repo(
                full_name="u/b",
                declarations=[PackageDeclaration("pypi", "ruamel-yaml", "direct")],
            ),
        ]
    )
    by_name = _by_name(skills)
    assert set(by_name) == {"ruamel-yaml"}
    assert len(by_name["ruamel-yaml"].evidence) == 2


def test_non_pypi_names_not_normalized() -> None:
    """pypi 以外（go 等）は package ID をそのまま canonical にすること。"""
    skills = aggregate_skills(
        [_repo(declarations=[PackageDeclaration("go", "github.com/Foo/Bar", "direct")])]
    )
    assert "github.com/Foo/Bar" in _by_name(skills)


def test_empty_repo_yields_no_skills() -> None:
    assert aggregate_skills([_repo()]) == []


def test_manifest_path_and_partial_propagate_to_package_evidence() -> None:
    """D9: source_path / partial が package 根拠へ伝播すること。"""
    repo = RepoSkillInput(
        full_name="u/mono",
        url="https://github.com/u/mono",
        languages={"Python": 1000},
        package_declarations=[
            PackageDeclaration(
                "pypi", "fastapi", "direct", source_path="backend/requirements.txt"
            )
        ],
        manifest_scan_partial=True,
    )
    by_name = _by_name(aggregate_skills([repo]))
    ev = by_name["fastapi"].evidence[0]
    assert ev.manifest_path == "backend/requirements.txt"
    assert ev.partial_scan is True


def test_partial_scan_not_set_on_language_evidence() -> None:
    """D9: partial は manifest 根拠のみ。language 根拠は常に False のままにすること。"""
    repo = RepoSkillInput(
        full_name="u/mono",
        url="https://github.com/u/mono",
        languages={"Python": 1000},
        package_declarations=[],
        manifest_scan_partial=True,
    )
    by_name = _by_name(aggregate_skills([repo]))
    lang_ev = by_name["Python"].evidence[0]
    assert lang_ev.partial_scan is False
    assert lang_ev.manifest_path is None
