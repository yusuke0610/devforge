"""スキルタクソノミパッケージ。

既存のインポートパスとの互換性を保つため、すべての公開シンボルを re-export する。
"""

from .classifier import (
    SKILL_CATEGORIES,
    get_all_skills,
    get_skill_category,
)
from .keyword_map import DESCRIPTION_KEYWORDS
from .language_map import LANGUAGE_TO_SKILL
from .topic_map import TOPIC_TO_SKILLS

__all__ = [
    "DESCRIPTION_KEYWORDS",
    "LANGUAGE_TO_SKILL",
    "SKILL_CATEGORIES",
    "TOPIC_TO_SKILLS",
    "get_all_skills",
    "get_skill_category",
]
