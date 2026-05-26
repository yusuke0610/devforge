"""GitHub 連携 API 用の Pydantic スキーマ。"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

# 進捗関連のスキーマは shared.py に移動済み。既存 import 経路を保つため re-export する。
from .shared import ProgressResponse, SubProgress  # noqa: F401


class GitHubLinkRequest(BaseModel):
    include_forks: bool = Field(
        False,
        description="連携にフォークしたリポジトリを含めるかどうか",
    )


class GitHubLinkResponse(BaseModel):
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


class CachedGitHubLinkResponse(BaseModel):
    """DB に保存された連携結果を返す。"""

    result: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    # 連携自体は完了したが部分的に欠落した場合の警告メッセージ
    warning_message: Optional[str] = None


