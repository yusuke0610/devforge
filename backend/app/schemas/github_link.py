"""GitHub 連携 API 用の Pydantic スキーマ。"""

from typing import Dict, List, Optional

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
    """1年分のコントリビューションカレンダー（GitHub の緑の四角）。"""

    year: int = Field(description="このカレンダーが対象とする西暦年")
    total_contributions: int = Field(description="期間内のコントリビューション総数")
    weeks: list[list[ContributionDay]] = Field(
        default_factory=list,
        description="週ごとの日配列（列=週、各週は最大7日）",
    )


class AnalyzedRepoSummary(BaseModel):
    """連携で分析したリポジトリ 1 件分のサマリ（ADR-0018）。

    経歴書ドラフト生成のルールベースマッピングが入力にする決定論データ。
    スキル証跡（github_skill_evidence）と同一連携実行時点のスナップショットになる。
    """

    full_name: str = Field(description="owner/name 形式のリポジトリ名")
    description: str = Field(default="", description="GitHub のリポジトリ説明（無ければ空文字）")
    created_at: str = Field(default="", description="ISO 8601 形式の作成日時")
    pushed_at: str = Field(default="", description="ISO 8601 形式の最終 push 日時")


class GitHubLinkResponse(BaseModel):
    username: str
    repos_analyzed: int
    unique_skills: int
    analyzed_at: str
    languages: Dict[str, int] = Field(
        default_factory=dict,
        description="言語ごとのバイト数（GitHub linguist ベース）",
    )
    contribution_calendars: List[ContributionCalendar] = Field(
        default_factory=list,
        description="年ごとのコントリビューションカレンダー（新しい年順。取得失敗時は空配列）",
    )
    # ADR-0018 以前に保存された旧形式 JSON には無いフィールド。default_factory で
    # 後方互換を保ち、旧形式かどうかは「空リスト」で判定する（ドラフト生成側で 409）
    repos: List[AnalyzedRepoSummary] = Field(
        default_factory=list,
        description="分析対象リポジトリのサマリ一覧（経歴書ドラフト生成の入力 / ADR-0018）",
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


