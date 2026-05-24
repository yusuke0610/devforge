"""キャリアインテリジェンス API 用の Pydantic スキーマ。"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# 進捗関連のスキーマは shared.py に移動済み。既存 import 経路を保つため re-export する。
from .shared import ProgressResponse, SubProgress  # noqa: F401


class AnalyzeRequest(BaseModel):
    include_forks: bool = Field(
        False,
        description="分析にフォークしたリポジトリを含めるかどうか",
    )


class PositionScoresResponse(BaseModel):
    """5軸のエンジニアポジションスコア。"""

    backend: int = Field(0, description="バックエンド適性スコア (0-100)")
    frontend: int = Field(0, description="フロントエンド適性スコア (0-100)")
    fullstack: int = Field(0, description="フルスタック適性スコア (0-100)")
    sre: int = Field(0, description="SRE適性スコア (0-100)")
    cloud: int = Field(0, description="クラウド適性スコア (0-100)")
    missing_skills: List[str] = Field(
        default_factory=list,
        description="フルスタックエンジニアに不足しているスキル",
    )


class AnalysisResponse(BaseModel):
    username: str
    repos_analyzed: int
    unique_skills: int
    analyzed_at: str
    languages: Dict[str, int] = Field(
        default_factory=dict,
        description="言語ごとのバイト数（GitHub linguist ベース）",
    )
    detected_frameworks: Dict[str, int] = Field(
        default_factory=dict,
        description="依存関係から検出したフレームワーク名 → 使用リポジトリ数",
    )
    detected_devtools: Dict[str, int] = Field(
        default_factory=dict,
        description="ルートファイルから検出した DevTools 名 → 使用リポジトリ数",
    )
    detected_infras: Dict[str, int] = Field(
        default_factory=dict,
        description="ルートファイルから検出したインフラツール名 → 使用リポジトリ数",
    )
    position_scores: Optional[PositionScoresResponse] = Field(
        None,
        description="エンジニアポジションスコア（5軸）",
    )


class PositionAdviceResponse(BaseModel):
    """現状分析+学習アドバイス。"""

    advice: str = Field("", description="LLM による現状分析と学習アドバイス")
    available: bool = Field(True, description="LLM サービスが利用可能かどうか")


class CachedAnalysisResponse(BaseModel):
    """DB に保存された分析結果・学習アドバイスを返す。"""

    analysis_result: Optional[Dict[str, Any]] = None
    position_advice: Optional[str] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    # 分析自体は完了したが LLM など部分的に欠落した場合の警告メッセージ
    warning_message: Optional[str] = None


