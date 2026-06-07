"""
キャリアインテリジェンスパイプラインのオーケストレーター。

GitHub のデータから以下の分析を順次実行します：
  GitHub → リポジトリ → 集計 → スキル抽出

各ステージは決定論的（LLM は呼ばない）。
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ...core.logging_utils import get_logger
from ...core.metrics import measure_time_async
from .github_collector import RepoData, collect_repos
from .skill_extractor import extract_skills

logger = get_logger(__name__)


@dataclass
class IntelligenceResult:
    """パイプラインの実行結果を保持するデータクラス。"""

    username: str
    repos_analyzed: int
    unique_skills: int
    analyzed_at: str
    languages: Dict[str, int] = field(default_factory=dict)


def aggregate_intelligence(username: str, repos: List[RepoData]) -> IntelligenceResult:
    """リポジトリ集合から ``IntelligenceResult`` を構築する純粋関数。

    I/O を行わないため、CLI/テスト向けの ``run_pipeline`` と
    進捗通知付きのバックグラウンドワーカーの双方から再利用できる。
    """
    lang_totals: Dict[str, int] = defaultdict(int)
    for repo in repos:
        for lang, byte_count in repo.languages.items():
            lang_totals[lang] += byte_count

    extraction = extract_skills(repos)

    return IntelligenceResult(
        username=username,
        repos_analyzed=extraction.repos_analyzed,
        unique_skills=len(extraction.unique_skills),
        analyzed_at=datetime.now().isoformat(),
        languages=dict(lang_totals),
    )


@measure_time_async("intelligence.pipeline")
async def run_pipeline(
    username: str,
    token: Optional[str] = None,
    include_forks: bool = False,
) -> IntelligenceResult:
    """GitHub ユーザーに対してキャリアインテリジェンスパイプラインを実行する。

    1. GitHub API からリポジトリ収集
    2. ``aggregate_intelligence`` で集計・スキル抽出
    """
    logger.info("%s のインテリジェンスパイプラインを開始します", username)

    repos: List[RepoData] = await collect_repos(
        username,
        token=token,
        include_forks=include_forks,
    )

    result = aggregate_intelligence(username, repos)

    logger.info(
        "パイプライン完了 (%s): 分析リポジトリ数=%d, ユニークスキル数=%d",
        username,
        result.repos_analyzed,
        result.unique_skills,
    )

    return result
