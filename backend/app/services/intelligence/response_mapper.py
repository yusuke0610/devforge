from typing import List

from ...schemas.github_link import AnalyzedRepoSummary, GitHubLinkResponse
from .github_collector import RepoData
from .pipeline import IntelligenceResult


def map_pipeline_result(
    result: IntelligenceResult, repos: List[RepoData] | None = None
) -> GitHubLinkResponse:
    """
    パイプラインの実行結果を API レスポンス形式に変換します。

    repos を渡すと、経歴書ドラフト生成（ADR-0018）の入力になるリポジトリ単位の
    サマリを ``repos`` フィールドに詰めて永続化対象へ含める。
    """
    repo_summaries = [
        AnalyzedRepoSummary(
            full_name=f"{repo.owner}/{repo.name}",
            description=repo.description,
            created_at=repo.created_at,
            pushed_at=repo.pushed_at,
        )
        for repo in (repos or [])
    ]
    return GitHubLinkResponse(
        username=result.username,
        repos_analyzed=result.repos_analyzed,
        unique_skills=result.unique_skills,
        analyzed_at=result.analyzed_at,
        languages=result.languages,
        repos=repo_summaries,
    )
