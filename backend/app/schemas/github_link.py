"""GitHub 連携 API 用の Pydantic スキーマ。"""

from typing import Dict, Optional

from pydantic import BaseModel, Field

# 進捗関連のスキーマは shared.py に移動済み。既存 import 経路を保つため re-export する。
from .shared import ProgressResponse, SubProgress  # noqa: F401


class GitHubLinkRequest(BaseModel):
    include_forks: bool = Field(
        False,
        description="連携にフォークしたリポジトリを含めるかどうか",
    )


class ContributionDay(BaseModel):
    """コントリビューションカレンダーの 1 日分。"""

    date: str = Field(description="ISO 8601 形式の日付 (YYYY-MM-DD)")
    count: int = Field(description="その日のコントリビューション数")
    level: int = Field(description="GitHub の濃淡レベル (0–4)")


class ContributionCalendar(BaseModel):
    """直近1年のコントリビューションカレンダー（GitHub の緑の四角）。"""

    total_contributions: int = Field(description="期間内のコントリビューション総数")
    weeks: list[list[ContributionDay]] = Field(
        default_factory=list,
        description="週ごとの日配列（列=週、各週は最大7日）",
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
    contribution_calendar: Optional[ContributionCalendar] = Field(
        default=None,
        description="直近1年のコントリビューションカレンダー（取得失敗時は None）",
    )


class CachedGitHubLinkResponse(BaseModel):
    """DB に保存された連携結果を返す。"""

    # cache.result は GitHubLinkResponse(...).model_dump() を保存したものなので、
    # 型を絞って OpenAPI に GitHubLinkResponse / Contribution* を出力させる（ADR-0007 Phase 2）。
    result: Optional[GitHubLinkResponse] = None
    status: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    # 連携自体は完了したが部分的に欠落した場合の警告メッセージ
    warning_message: Optional[str] = None


