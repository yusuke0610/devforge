"""
キャリアインテリジェンスパイプラインの集計関数。

GitHub から収集したリポジトリ集合（``RepoData``）と、スキル推論基盤
（ADR-0016 / ``skills.aggregate_skills``）が組み立てた ``DetectedSkill`` 列から、
dashboard 表示用の集計結果（``IntelligenceResult``）を構築する。

集計は決定論的（LLM は呼ばない）。スキルの正規化・検出は ``skills/`` 配下が担い、
本モジュールは「件数・言語バイト数」の表示用サマリ算出に責務を限定する。
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from .github_collector import RepoData
from .skills import DetectedSkill
from .skills.types import SKILL_KIND_LANGUAGE


@dataclass
class IntelligenceResult:
    """パイプラインの実行結果を保持するデータクラス。"""

    username: str
    repos_analyzed: int
    unique_skills: int
    analyzed_at: str
    languages: Dict[str, int] = field(default_factory=dict)


def aggregate_intelligence(
    username: str,
    repos: List[RepoData],
    detected_skills: List[DetectedSkill],
) -> IntelligenceResult:
    """リポジトリ集合と検出スキルから ``IntelligenceResult`` を構築する純粋関数。

    I/O を行わない。``unique_skills`` は ADR-0016 のスキル推論基盤が検出した
    Layer 1 スキルのうち **言語スキル（kind=language）の件数**を表す
    （dashboard 表示用。package は件数に含めない）。旧辞書ベース抽出は撤去済み。
    ``languages`` は Linguist のバイト数をリポジトリ横断で合算する。
    """
    lang_totals: Dict[str, int] = defaultdict(int)
    for repo in repos:
        for lang, byte_count in repo.languages.items():
            lang_totals[lang] += byte_count

    unique_language_skills = sum(
        1 for skill in detected_skills if skill.kind == SKILL_KIND_LANGUAGE
    )

    return IntelligenceResult(
        username=username,
        repos_analyzed=len(repos),
        unique_skills=unique_language_skills,
        analyzed_at=datetime.now().isoformat(),
        languages=dict(lang_totals),
    )
