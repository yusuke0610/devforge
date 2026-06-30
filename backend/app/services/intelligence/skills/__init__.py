"""GitHub 連携スキル推論基盤（ADR-0016）。

discover（言語 / Linguist）+ declare（manifest 宣言）+ verify（import 解析）を合流し、
3 層モデルへ投入する中間表現を組み立てる。
"""

from .aggregator import (
    DetectedSkill,
    EvidenceRecord,
    RepoSkillInput,
    aggregate_skills,
)
from .types import PackageDeclaration

__all__ = [
    "DetectedSkill",
    "EvidenceRecord",
    "PackageDeclaration",
    "RepoSkillInput",
    "aggregate_skills",
]
