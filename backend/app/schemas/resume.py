"""職務経歴書（Resume）の Pydantic スキーマ。

FE 同期: 本モジュールの各 Item / レスポンス型は ``frontend/src/types.ts`` の Career 系 type
（``ResumeQualification`` / ``CareerTechnologyStack`` / ``TeamMember`` / ``ProjectTeam`` /
``CareerProject`` / ``CareerClient`` / ``CareerExperience`` 等）と対になる DTO。
言語境界のため codegen 未導入の手動同期で運用している（エラーコードの errors.py と同方針）。
フィールドを増減・rename する場合は対応する FE type も同時に更新すること。
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from ..core.date_utils import to_jst
from ..core.messages import get_error


class ResumeQualificationItem(BaseModel):
    # 取得年月・名称ともに必須（保存時にフロント payloadBuilders も必須を強制する）。
    # PDF インポートで日付が無い場合はプレビュー用 ImportQualificationItem が許容し、
    # 保存前にユーザーがフォームで日付を補完する運用とする。
    acquired_date: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(from_attributes=True)


class TechnologyStackItem(BaseModel):
    category: Literal[
        "language",
        "framework",
        "os",
        "db",
        "cloud_provider",
        "container",
        "iac",
        "vcs",
        "ci_cd",
        "project_tool",
        "monitoring",
        "middleware",
        "ai_agent",
    ]
    name: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(from_attributes=True)


class TeamMember(BaseModel):
    """体制の役割ごとの人数。"""

    role: str = Field(max_length=60)
    count: int = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class ProjectTeam(BaseModel):
    """プロジェクト体制（全体人数 + 役割別内訳）。"""

    total: str = Field(max_length=60, default="")
    members: list[TeamMember] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class Project(BaseModel):
    name: str = Field(max_length=200, default="")
    start_date: str = Field(max_length=30, default="")
    # 参画中（is_current=True）の場合は "" を渡す契約。
    # DB 上 end_date は NULL で保存され、ResumeProject.end_date プロパティが "" を返す。
    end_date: str = Field(default="", max_length=30)
    is_current: bool = False
    role: str = Field(max_length=200, default="")
    # 課題・行動・成果を統合した自由記述欄（見出し「詳細」）
    description: str = Field(max_length=4500, default="")
    team: ProjectTeam = Field(default_factory=ProjectTeam)
    technology_stacks: list[TechnologyStackItem] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _migrate_scale_to_team(cls, data: dict) -> dict:
        """旧形式 scale → team に自動変換する後方互換処理。"""
        if isinstance(data, dict) and "scale" in data and "team" not in data:
            scale = data.pop("scale")
            data["team"] = {"total": str(scale) if scale else "", "members": []}
        return data

    @model_validator(mode="after")
    def validate_dates(self) -> "Project":
        """開始年月を必須化し、参画中でなければ終了年月も必須化、日付範囲を検証する。

        開始年月が空のまま repositories 層に渡ると ``parse_year_month("")`` が
        ValueError を投げて 500 になる（DB の start_date は NOT NULL）。
        手前で 422（日本語メッセージ）として返す。フロントは案件に内容がある行のみ
        送信するため、ここに到達するプロジェクトは開始年月が必須でよい。
        """
        if not self.start_date.strip():
            raise ValueError(get_error("validation.start_date_required"))
        if self.is_current:
            self.end_date = ""
            return self
        if not self.end_date.strip():
            raise ValueError(get_error("validation.end_date_required"))
        if self.end_date < self.start_date:
            raise ValueError(get_error("validation.date_range_invalid"))
        return self


class Client(BaseModel):
    """ユーザ（常駐先/クライアント企業）。"""

    name: str = Field(max_length=200, default="")
    has_client: bool = True
    projects: list[Project] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class Experience(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    business_description: str = Field(min_length=1, max_length=200)
    # 在籍開始年月は必須だが、空欄時に日本語メッセージを返すため min_length ではなく
    # validate_dates で検証する（English な Pydantic 既定メッセージを避ける）。
    # 従業員数・資本金は会社名があっても任意入力のまま（required にしない）。
    start_date: str = Field(default="", max_length=30)
    end_date: str = Field(default="", max_length=30)
    is_current: bool = False
    employee_count: str = Field(max_length=60, default="")
    capital: str = Field(max_length=120, default="")
    clients: list[Client] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _migrate_projects_to_clients(cls, data: dict) -> dict:
        """旧形式（projects直下）を clients にラップする後方互換処理。"""
        if isinstance(data, dict) and "projects" in data and "clients" not in data:
            projects = data.pop("projects")
            data["clients"] = [{"name": "", "projects": projects}]
        return data

    @model_validator(mode="after")
    def validate_dates(self) -> "Experience":
        """在籍開始年月の必須チェック、終了年月の必須チェック、日付範囲の検証を行う。

        開始年月が空のまま repositories 層に渡ると ``parse_year_month("")`` が
        ValueError を投げて 500 になる。手前で 422（日本語メッセージ）として返す。
        """
        if not self.start_date.strip():
            raise ValueError(get_error("validation.start_date_required"))
        if self.is_current:
            self.end_date = ""
            return self
        if not self.end_date.strip():
            raise ValueError(get_error("validation.end_date_required"))
        if self.end_date < self.start_date:
            raise ValueError(get_error("validation.date_range_invalid"))
        return self


class ResumeBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    career_summary: str = Field(min_length=1, max_length=2000)
    self_pr: str = Field(min_length=1, max_length=2000)
    experiences: list[Experience] = Field(default_factory=list)
    qualifications: list[ResumeQualificationItem] = Field(default_factory=list)


class ResumeCreate(ResumeBase):
    pass


class ResumeUpdate(ResumeBase):
    pass


class ResumeResponse(ResumeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def serialize_as_jst(self, dt: datetime) -> str:
        """UTC datetime を JST (UTC+9) の ISO 8601 文字列にシリアライズする。"""
        return to_jst(dt).isoformat()
