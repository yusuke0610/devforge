from ...schemas.github_link import GitHubLinkResponse
from .pipeline import IntelligenceResult


def map_pipeline_result(result: IntelligenceResult) -> GitHubLinkResponse:
    """
    パイプラインの実行結果を API レスポンス形式に変換します。
    """
    return GitHubLinkResponse(
        username=result.username,
        repos_analyzed=result.repos_analyzed,
        unique_skills=result.unique_skills,
        analyzed_at=result.analyzed_at,
        languages=result.languages,
    )
