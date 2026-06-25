"""スキル集計（discover + declare の合流 / ADR-0016 D1・D5）。

リポジトリ集合（言語バイト数 + manifest 宣言）から Layer 1（正規化スキル）と
Layer 2（技術×リポの根拠）の中間表現を組み立てる純粋関数。I/O は行わない。

「保持は細かく」（D8）に従い、検出された根拠は全リポ分そのまま保持し、
足切り・粒度畳みは後段のビュー変換に委ねる（ここでは非可逆な切り捨てをしない）。
"""

from dataclasses import dataclass, field

from .linguist import resolve_language
from .types import (
    SKILL_KIND_LANGUAGE,
    SKILL_KIND_PACKAGE,
    PackageDeclaration,
)

# package の dependency_kind ごとの信頼度（manifest 宣言のみ。実使用は verify で昇格）。
_DEPENDENCY_CONFIDENCE = {
    "direct": 0.6,
    "peer": 0.4,
    "build": 0.3,
    "dev": 0.3,
    "indirect": 0.1,
}
_SIGNAL_LANGUAGE_BYTES = "language_bytes"
_SIGNAL_MANIFEST_DECLARED = "manifest_declared"


@dataclass(frozen=True)
class EvidenceRecord:
    """Layer 2 の 1 根拠。"""

    repo_full_name: str
    repo_url: str
    signal_source: str
    confidence: float
    language_bytes: int | None = None
    dependency_kind: str | None = None


@dataclass
class DetectedSkill:
    """Layer 1 のスキルと、それに紐づく Layer 2 根拠の束。"""

    kind: str
    canonical_name: str
    ecosystem: str
    parent: str | None
    display_name: str | None
    evidence: list[EvidenceRecord] = field(default_factory=list)


@dataclass
class RepoSkillInput:
    """1 リポジトリ分の集計入力（aggregator が依存する最小形）。"""

    full_name: str  # owner/name
    url: str
    languages: dict[str, int]
    package_declarations: list[PackageDeclaration] = field(default_factory=list)


def aggregate_skills(repos: list[RepoSkillInput]) -> list[DetectedSkill]:
    """リポジトリ集合から ``DetectedSkill`` 列を組み立てる。

    同一スキル（kind + ecosystem + canonical）は 1 件に畳み、根拠（evidence）を集約する。
    """
    # キー = (kind, ecosystem, canonical_name)
    skills: dict[tuple[str, str, str], DetectedSkill] = {}

    for repo in repos:
        _collect_languages(skills, repo)
        _collect_packages(skills, repo)

    return list(skills.values())


def _upsert(
    skills: dict[tuple[str, str, str], DetectedSkill],
    *,
    kind: str,
    canonical_name: str,
    ecosystem: str,
    parent: str | None,
    display_name: str | None,
) -> DetectedSkill:
    key = (kind, ecosystem, canonical_name)
    skill = skills.get(key)
    if skill is None:
        skill = DetectedSkill(
            kind=kind,
            canonical_name=canonical_name,
            ecosystem=ecosystem,
            parent=parent,
            display_name=display_name,
        )
        skills[key] = skill
    return skill


def _collect_languages(
    skills: dict[tuple[str, str, str], DetectedSkill], repo: RepoSkillInput
) -> None:
    total_bytes = sum(repo.languages.values())
    if total_bytes <= 0:
        return
    for lang, byte_count in repo.languages.items():
        resolved = resolve_language(lang)
        if resolved is None:
            continue
        display = (
            resolved.display if resolved.display != resolved.canonical else None
        )
        skill = _upsert(
            skills,
            kind=SKILL_KIND_LANGUAGE,
            canonical_name=resolved.canonical,
            ecosystem="",
            parent=resolved.parent,
            display_name=display,
        )
        skill.evidence.append(
            EvidenceRecord(
                repo_full_name=repo.full_name,
                repo_url=repo.url,
                signal_source=_SIGNAL_LANGUAGE_BYTES,
                confidence=round(byte_count / total_bytes, 4),
                language_bytes=byte_count,
            )
        )


def _collect_packages(
    skills: dict[tuple[str, str, str], DetectedSkill], repo: RepoSkillInput
) -> None:
    # 同一リポ内で同じ package が複数 kind で宣言された場合は最も強い根拠を採用する
    # （例: dependencies と devDependencies の両方に出現）。
    best: dict[tuple[str, str], PackageDeclaration] = {}
    for decl in repo.package_declarations:
        if not decl.name:
            continue
        key = (decl.ecosystem, decl.name)
        current = best.get(key)
        if current is None or _confidence(decl.dependency_kind) > _confidence(
            current.dependency_kind
        ):
            best[key] = decl

    for (ecosystem, name), decl in best.items():
        skill = _upsert(
            skills,
            kind=SKILL_KIND_PACKAGE,
            canonical_name=name,
            ecosystem=ecosystem,
            parent=None,
            display_name=None,
        )
        skill.evidence.append(
            EvidenceRecord(
                repo_full_name=repo.full_name,
                repo_url=repo.url,
                signal_source=_SIGNAL_MANIFEST_DECLARED,
                confidence=_confidence(decl.dependency_kind),
                dependency_kind=decl.dependency_kind,
            )
        )


def _confidence(dependency_kind: str | None) -> float:
    return _DEPENDENCY_CONFIDENCE.get(dependency_kind or "", 0.2)
