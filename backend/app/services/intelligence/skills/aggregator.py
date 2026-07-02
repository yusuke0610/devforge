"""スキル集計（discover + declare の合流 / ADR-0016 D1・D5）。

リポジトリ集合（言語バイト数 + manifest 宣言）から Layer 1（正規化スキル）と
Layer 2（技術×リポの根拠）の中間表現を組み立てる純粋関数。I/O は行わない。

「保持は細かく」（D8）に従い、検出された根拠は全リポ分そのまま保持し、
足切り・粒度畳みは後段のビュー変換に委ねる（ここでは非可逆な切り捨てをしない）。
"""

import re
from dataclasses import dataclass, field

from .imports import scanner_for_ecosystem
from .linguist import resolve_language
from .types import (
    SKILL_KIND_INFRA,
    SKILL_KIND_LANGUAGE,
    SKILL_KIND_PACKAGE,
    InfraResourceDeclaration,
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
# verify（D6）: direct 宣言が実際に import されていたときの昇格後 confidence。
_ACTUAL_IMPORT_CONFIDENCE = 0.85
_SIGNAL_LANGUAGE_BYTES = "language_bytes"
_SIGNAL_MANIFEST_DECLARED = "manifest_declared"
_SIGNAL_ACTUAL_IMPORT = "actual_import"
# D10: IaC の宣言（provider / resource）。宣言 ≒ 実構築に近く verify 昇格は行わない。
_SIGNAL_INFRA_DECLARED = "infra_declared"
# D10: infra 宣言の信頼度。resource（具体サービス）は provider より使用実績が明確なので高め。
_INFRA_PROVIDER_CONFIDENCE = 0.5
_INFRA_RESOURCE_CONFIDENCE = 0.6

# PEP 503 正規化用（連続する -_. を - に畳む）。
_PYPI_NAME_RE = re.compile(r"[-_.]+")


def _canonical_package_name(ecosystem: str, name: str) -> str:
    """エコシステム内で一意な canonical 名へ正規化する。

    pypi のみ PEP 503 正規化（小文字化・区切り統一）し、``Flask``/``flask`` や
    ``ruamel.yaml``/``ruamel-yaml`` を同一視する。他エコシステムは package ID を
    そのまま canonical とする（D3）。
    """
    if ecosystem == "pypi":
        return _PYPI_NAME_RE.sub("-", name).lower()
    return name


@dataclass(frozen=True)
class EvidenceRecord:
    """Layer 2 の 1 根拠。"""

    repo_full_name: str
    repo_url: str
    signal_source: str
    confidence: float
    language_bytes: int | None = None
    dependency_kind: str | None = None
    # D9(f): manifest の相対パス（package 根拠のみ。language では None）。
    manifest_path: str | None = None
    # D9(d): 部分スキャン由来か（manifest 根拠のみ True になりうる。language は常に False）。
    partial_scan: bool = False


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
    # verify（D6）: import 解析で実使用が確認された名前の集合（ecosystem → import 名）。
    imported_symbols: dict[str, set[str]] = field(default_factory=dict)
    # D9(d): このリポのツリー走査が部分的だったか。package 根拠へ伝播する。
    manifest_scan_partial: bool = False
    # D10: IaC（.tf）が宣言する provider / resource。
    infra_declarations: list[InfraResourceDeclaration] = field(default_factory=list)
    # D10: IaC 走査が部分的だったか。infra 根拠へ伝播する。
    infra_scan_partial: bool = False


def aggregate_skills(repos: list[RepoSkillInput]) -> list[DetectedSkill]:
    """リポジトリ集合から ``DetectedSkill`` 列を組み立てる。

    同一スキル（kind + ecosystem + canonical）は 1 件に畳み、根拠（evidence）を集約する。
    """
    # キー = (kind, ecosystem, canonical_name)
    skills: dict[tuple[str, str, str], DetectedSkill] = {}

    for repo in repos:
        _collect_languages(skills, repo)
        _collect_packages(skills, repo)
        _collect_infra(skills, repo)

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
        # canonical 名でキーを作る（pypi は PEP 503 正規化で大小文字・区切り差を畳む）。
        name = _canonical_package_name(decl.ecosystem, decl.name)
        key = (decl.ecosystem, name)
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
                # D9(f): 採用した宣言の manifest パスを証跡として残す。
                manifest_path=decl.source_path,
                # D9(d): partial は manifest 根拠にのみ立てる（language には立てない）。
                partial_scan=repo.manifest_scan_partial,
            )
        )
        # verify（D6）: direct 宣言が実際に import されていたら actual_import 証跡を **追加**する。
        # declare 証跡は残したまま昇格証跡を足す（昇格のみ・降格なし / 保持は細かく / D8）。
        if decl.dependency_kind == "direct" and _is_imported(
            ecosystem, name, repo.imported_symbols
        ):
            skill.evidence.append(
                EvidenceRecord(
                    repo_full_name=repo.full_name,
                    repo_url=repo.url,
                    signal_source=_SIGNAL_ACTUAL_IMPORT,
                    confidence=_ACTUAL_IMPORT_CONFIDENCE,
                    dependency_kind=decl.dependency_kind,
                    manifest_path=decl.source_path,
                    partial_scan=repo.manifest_scan_partial,
                )
            )


def _collect_infra(
    skills: dict[tuple[str, str, str], DetectedSkill], repo: RepoSkillInput
) -> None:
    """IaC 宣言（provider / resource）を kind=infra スキルへ集約する（declare 相当 / D10）。

    provider（``aws``）と resource type（``aws_s3_bucket``）を別スキルとして keep-all する
    （畳み込みは後段 HITL に委ねる / D8）。同一リポ内で同じ provider / resource が複数の .tf に
    現れても、``github_skill_evidence`` の一意制約 (skill_id, repo, signal_source) に合わせて
    **リポあたり 1 根拠**にデデュープする（最初に見た source_path を証跡に採る）。
    """
    # canonical → 最初に採用する宣言（source_path 付き）。リポ内で 1 evidence に畳む。
    provider_seen: dict[str, InfraResourceDeclaration] = {}
    resource_seen: dict[str, InfraResourceDeclaration] = {}
    for decl in repo.infra_declarations:
        if decl.provider and decl.provider not in provider_seen:
            provider_seen[decl.provider] = decl
        if decl.resource_type and decl.resource_type not in resource_seen:
            resource_seen[decl.resource_type] = decl

    for provider, decl in provider_seen.items():
        _append_infra_skill(
            skills, repo, decl, provider, _INFRA_PROVIDER_CONFIDENCE
        )
    for resource_type, decl in resource_seen.items():
        _append_infra_skill(
            skills, repo, decl, resource_type, _INFRA_RESOURCE_CONFIDENCE
        )


def _append_infra_skill(
    skills: dict[tuple[str, str, str], DetectedSkill],
    repo: RepoSkillInput,
    decl: InfraResourceDeclaration,
    canonical_name: str,
    confidence: float,
) -> None:
    """1 つの infra スキル（provider or resource）を upsert し根拠を積む。"""
    # ecosystem は IaC ツール名（"terraform"）。将来の Pulumi / CloudFormation と区別する。
    skill = _upsert(
        skills,
        kind=SKILL_KIND_INFRA,
        canonical_name=canonical_name,
        ecosystem=decl.tool,
        parent=None,
        display_name=None,
    )
    skill.evidence.append(
        EvidenceRecord(
            repo_full_name=repo.full_name,
            repo_url=repo.url,
            signal_source=_SIGNAL_INFRA_DECLARED,
            confidence=confidence,
            # D9(f): 検出した .tf の相対パスを証跡として残す。
            manifest_path=decl.source_path,
            partial_scan=repo.infra_scan_partial,
        )
    )


def _confidence(dependency_kind: str | None) -> float:
    return _DEPENDENCY_CONFIDENCE.get(dependency_kind or "", 0.2)


def _is_imported(
    ecosystem: str, canonical_name: str, imported_symbols: dict[str, set[str]]
) -> bool:
    """canonical 名がこのリポの import 解析結果（verify / D6）で実使用されていたか。

    照合規則（``-``→``_`` 変換・接頭辞一致など）はエコシステム別スキャナに委譲する。
    未対応エコシステム・スキャン結果なしは False（昇格しないだけで declare 証跡は残る）。
    """
    scanner = scanner_for_ecosystem(ecosystem)
    if scanner is None:
        return False
    return scanner.matches(canonical_name, imported_symbols.get(ecosystem, set()))
