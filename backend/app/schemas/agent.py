"""DevForge Agent（LLM チャット）の Pydantic スキーマ（ADR-0010）。

リクエストの ``resume`` は保存用の ``ResumeCreate`` ではなく緩い専用コンテキスト型を使う。
ユーザーが編集途中のフォーム（必須項目が未入力・日付未設定など保存契約を満たさない状態）
から Agent を呼べる必要があり、保存時バリデーションを再利用すると 422 になるため。
フィールドの max_length は保存契約（``resume.py``）と同じ上限に揃える。

レスポンスの ``operations`` はテキストフィールドの置換のみ（構造編集なし、Phase 1）。
スコープ選択が必須で対象 project の位置はリクエストで確定するため、operation は
パス指定を持たず「フィールド名 + 新しい値」だけを返す。
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from ..core.messages import get_error

AgentScope = Literal["project", "career_summary", "self_pr"]

# operation が編集できるフィールド（Phase 1 はテキストのみ）
AgentField = Literal["career_summary", "self_pr", "description", "role"]


class AgentTechnologyStack(BaseModel):
    """LLM コンテキスト用の技術スタック（保存契約より緩い）。"""

    category: str = Field(default="", max_length=60)
    name: str = Field(default="", max_length=120)


class AgentProjectContext(BaseModel):
    """LLM コンテキスト用のプロジェクト情報。"""

    name: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4500)
    technology_stacks: list[AgentTechnologyStack] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)


class AgentClientContext(BaseModel):
    """LLM コンテキスト用の取引先情報。"""

    name: str = Field(default="", max_length=200)
    projects: list[AgentProjectContext] = Field(default_factory=list)


class AgentExperienceContext(BaseModel):
    """LLM コンテキスト用の在籍企業情報。"""

    company: str = Field(default="", max_length=120)
    business_description: str = Field(default="", max_length=200)
    clients: list[AgentClientContext] = Field(default_factory=list)


class AgentResumeContext(BaseModel):
    """LLM に渡す編集中の職務経歴書コンテキスト。

    保存契約（必須項目・日付検証）は適用しない。DB は参照せず、
    フロントが編集中のフォーム内容をそのまま送る設計（DB を更新しない原則）。
    """

    career_summary: str = Field(default="", max_length=2000)
    self_pr: str = Field(default="", max_length=2000)
    experiences: list[AgentExperienceContext] = Field(default_factory=list)


class ProjectTarget(BaseModel):
    """scope=project のとき対象プロジェクトを特定するインデックス。"""

    experience_index: int = Field(ge=0)
    client_index: int = Field(ge=0)
    project_index: int = Field(ge=0)


class AgentChatRequest(BaseModel):
    """Agent チャットのリクエスト。スコープ選択は必須。"""

    scope: AgentScope
    prompt: str = Field(min_length=1, max_length=2000)
    resume: AgentResumeContext
    target: ProjectTarget | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "AgentChatRequest":
        """project スコープでは対象プロジェクトの指定を必須とする。"""
        if self.scope == "project" and self.target is None:
            raise ValueError(get_error("agent.target_required"))
        return self


class AgentOperation(BaseModel):
    """resume state へ適用する差分（テキストフィールドの置換）。

    フロントは選択済みスコープ（と target）に対応するフィールドへ value を反映する。
    DB は更新せず、ユーザーが「適用」した時点で既存の保存 API を呼ぶ。
    """

    field: AgentField
    value: str = Field(max_length=4500)


class AgentChatResponse(BaseModel):
    """Agent チャットのレスポンス（AI の説明文 + 差分 operations）。"""

    message: str
    operations: list[AgentOperation] = Field(default_factory=list)
