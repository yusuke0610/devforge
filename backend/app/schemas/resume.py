from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from ..core.date_utils import to_jst
from ..core.messages import get_error


class ResumeQualificationItem(BaseModel):
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
    # 参画中（is_current=True）のプロジェクトは DB 上 end_date が NULL となり、
    # ResumeProject.end_date プロパティが None を返す。
    # Experience.end_date と同様に str | None を許容することでレスポンスの整合性を取る。
    end_date: str | None = Field(default=None, max_length=30)
    is_current: bool = False
    role: str = Field(max_length=200, default="")
    description: str = Field(max_length=1500, default="")
    challenge: str = Field(max_length=1500, default="")
    action: str = Field(max_length=1500, default="")
    result: str = Field(max_length=1500, default="")
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
    def validate_date_range(self) -> "Project":
        """終了日が開始日より前でないことを検証する。"""
        if self.start_date and self.end_date and not self.is_current:
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
    start_date: str = Field(min_length=1, max_length=30)
    end_date: str | None = Field(default=None, max_length=30)
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
    def validate_end_date(self) -> "Experience":
        """終了日の必須チェックと日付範囲の検証を行う。"""
        if self.is_current:
            self.end_date = None
            return self
        if not self.end_date or not self.end_date.strip():
            raise ValueError(get_error("validation.end_date_required"))
        if self.start_date and self.end_date < self.start_date:
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
