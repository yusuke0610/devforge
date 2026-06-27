"""GitHub 連携 API の ORM → レスポンススキーマ変換。

HTTP 出力整形（プレゼンテーション層）を endpoints から分離する
（.claude/rules/common/duplication.md の Backend ヒエラルキー「routers/<scope>/_responses.py」）。
"""

from ...schemas.github_skill import (
    GitHubSkillItem,
    SkillEvidence,
    SkillProficiency,
)


def to_skill_item(skill) -> GitHubSkillItem:
    """ORM の GitHubSkill を API スキーマへ変換する。"""
    proficiency = None
    if skill.proficiency is not None:
        proficiency = SkillProficiency(
            self_assessed_level=skill.proficiency.self_assessed_level,
            narrative=skill.proficiency.narrative,
            duration_months=skill.proficiency.duration_months,
            scale=skill.proficiency.scale,
            source=skill.proficiency.source,
            reviewed=skill.proficiency.reviewed,
        )
    return GitHubSkillItem(
        kind=skill.kind,
        canonical_name=skill.canonical_name,
        # 言語は ecosystem を "" で持つので API では null に正規化する
        ecosystem=skill.ecosystem or None,
        parent=skill.parent,
        display_name=skill.display_name,
        evidence=[
            SkillEvidence(
                repo_full_name=ev.repo_full_name,
                repo_url=ev.repo_url,
                signal_source=ev.signal_source,
                confidence=ev.confidence,
                language_bytes=ev.language_bytes,
                dependency_kind=ev.dependency_kind,
                manifest_path=ev.manifest_path,
                partial_scan=ev.partial_scan,
            )
            for ev in skill.evidence
        ],
        proficiency=proficiency,
    )
