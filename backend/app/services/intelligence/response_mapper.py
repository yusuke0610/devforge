from typing import List

from ...schemas.github_link import AnalyzedRepoSummary, GitHubLinkResponse
from .github_collector import RepoData
from .pipeline import IntelligenceResult
from .skills.types import DEPENDENCY_KIND_DIRECT


def _to_repo_summary(repo: RepoData) -> AnalyzedRepoSummary:
    """収集層の RepoData を永続化用サマリへ写す（ADR-0026 決定 4）。

    シグナルはすべて連携実行時に取得済みの値から算出する。GitHub API は叩かない。
    """
    return AnalyzedRepoSummary(
        full_name=f"{repo.owner}/{repo.name}",
        description=repo.description,
        created_at=repo.created_at,
        pushed_at=repo.pushed_at,
        topics=list(repo.topics),
        language_bytes_total=sum(repo.languages.values()),
        # dev / indirect / peer / build は開発補助・推移的依存であり、リポジトリの
        # 実装内容を表さないため厚みに数えない（ADR-0026 決定 4）
        direct_dependency_count=sum(
            1
            for decl in repo.package_declarations
            if decl.dependency_kind == DEPENDENCY_KIND_DIRECT
        ),
        ecosystem_count=len({decl.ecosystem for decl in repo.package_declarations}),
        has_infra=bool(repo.infra_declarations),
    )


def map_pipeline_result(
    result: IntelligenceResult, repos: List[RepoData] | None = None
) -> GitHubLinkResponse:
    """
    パイプラインの実行結果を API レスポンス形式に変換します。

    repos を渡すと、経歴書ドラフト生成（ADR-0018）の入力になるリポジトリ単位の
    サマリを ``repos`` フィールドに詰めて永続化対象へ含める。
    """
    repo_summaries = [_to_repo_summary(repo) for repo in (repos or [])]
    return GitHubLinkResponse(
        username=result.username,
        repos_analyzed=result.repos_analyzed,
        unique_skills=result.unique_skills,
        analyzed_at=result.analyzed_at,
        languages=result.languages,
        repos=repo_summaries,
    )
