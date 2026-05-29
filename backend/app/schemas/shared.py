"""ドメイン横断で共用する Pydantic スキーマ。"""

from typing import Optional

from pydantic import BaseModel, Field

_HIRAGANA_PATTERN = r"^[ぁ-ゖー\s　]+$"


class TaskStatusResponse(BaseModel):
    """非同期タスクのステータスを返す軽量レスポンス。

    blog / intelligence など複数の router で共通利用される。
    """

    status: str
    error_message: str | None = None
    error_code: str | None = None


class TaskAcceptedResponse(BaseModel):
    """非同期タスクの受付応答（202 Accepted）。

    ``POST /github/run`` / ``POST /github/run/retry`` など、
    バックグラウンドタスクを開始するエンドポイントで共通利用される受付レスポンス。
    現在のタスクステータス（``pending`` 等）のみを返す。
    """

    status: str


class SubProgress(BaseModel):
    """ステップ内の細粒度な進捗（例: リポジトリ詳細取得ステップ）。"""

    done: int
    total: int


class ProgressResponse(BaseModel):
    """非同期タスクの進捗情報。

    GitHub 連携 / resume_import など、複数ステップを持つタスクで共通利用される。
    """

    task_id: str
    step_index: int = Field(0, description="現在のステップ番号（0 は未開始）")
    total_steps: int = Field(5, description="全ステップ数")
    step_label: Optional[str] = Field(None, description="現在のステップラベル")
    sub_progress: Optional[SubProgress] = Field(
        None, description="ステップ内の細粒度進捗（任意）"
    )
