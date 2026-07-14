"""スキル表示名の human-in-the-loop 畳み込み提案（ADR-0016 D11）。

agent は実在スキル群から表示名・畳み込みグループを **提案するだけ**（D8 / P4）で、
確定・永続化は人間 → repository が担う。Agent の不変条件（制約の責務分離・リトライ 1 回・
エラー契約・DB 非更新）を継承する。
"""

from .proposer import (
    MAX_SKILLS_PER_PROPOSAL,
    ProposedGroup,
    SkillDisplayProposalResult,
    SkillForProposal,
    SkillIdentity,
    propose_skill_display_names,
)

__all__ = [
    "MAX_SKILLS_PER_PROPOSAL",
    "ProposedGroup",
    "SkillDisplayProposalResult",
    "SkillForProposal",
    "SkillIdentity",
    "propose_skill_display_names",
]
