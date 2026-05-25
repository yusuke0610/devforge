from ...schemas.intelligence import AnalysisResponse
from .pipeline import IntelligenceResult


def map_pipeline_result(result: IntelligenceResult) -> AnalysisResponse:
    """
    パイプラインの実行結果を API レスポンス形式に変換します。
    """
    return AnalysisResponse(
        username=result.username,
        repos_analyzed=result.repos_analyzed,
        unique_skills=result.unique_skills,
        analyzed_at=result.analyzed_at,
        languages=result.languages,
        detected_frameworks=result.detected_frameworks,
        detected_devtools=result.detected_devtools,
        detected_infras=result.detected_infras,
    )
