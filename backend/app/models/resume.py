import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.date_utils import format_year_month
from ..db import Base
from ..services.shared.sort_utils import sort_by_date_asc, sort_by_period_desc


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (UniqueConstraint("user_id", name="uq_resumes_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    career_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    self_pr: Mapped[str] = mapped_column(Text, nullable=False)
    experience_rows: Mapped[list["ResumeExperience"]] = relationship(
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="ResumeExperience.sort_order",
    )
    qualification_rows: Mapped[list["ResumeQualification"]] = relationship(
        back_populates="resume",
        cascade="all, delete-orphan",
        order_by="ResumeQualification.sort_order",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def experiences(self) -> list["ResumeExperience"]:
        """経歴を在籍期間の降順でソートして返す。"""
        return sort_by_period_desc(list(self.experience_rows))

    @property
    def qualifications(self) -> list["ResumeQualification"]:
        """資格を取得日の昇順でソートして返す。"""
        return sort_by_date_asc(list(self.qualification_rows), date_key="acquired_date_value")


class ResumeQualification(Base):
    __tablename__ = "resume_qualifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resume_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acquired_date_value: Mapped[date] = mapped_column("acquired_date", Date, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    resume: Mapped["Resume"] = relationship(back_populates="qualification_rows")

    @property
    def acquired_date(self) -> str:
        # 在籍期間と同じく YYYY-MM で返す（UI は type="month" に統一）。
        return format_year_month(self.acquired_date_value) or ""


class ResumeExperience(Base):
    __tablename__ = "resume_experiences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    resume_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    company: Mapped[str] = mapped_column(String(120), nullable=False)
    business_description: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date_value: Mapped[date] = mapped_column("start_date", Date, nullable=False)
    end_date_value: Mapped[date | None] = mapped_column("end_date", Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    employee_count: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    capital: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    client_rows: Mapped[list["ResumeClient"]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        order_by="ResumeClient.sort_order",
    )
    resume: Mapped["Resume"] = relationship(back_populates="experience_rows")

    @property
    def start_date(self) -> str:
        return format_year_month(self.start_date_value) or ""

    @property
    def end_date(self) -> str:
        """DB の end_date が NULL（在籍中）の場合は "" を返す（schema 契約と一致）。"""
        return format_year_month(self.end_date_value) or ""

    @property
    def clients(self) -> list["ResumeClient"]:
        return list(self.client_rows)


class ResumeClient(Base):
    __tablename__ = "resume_clients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    experience_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resume_experiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    has_client: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    project_rows: Mapped[list["ResumeProject"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="ResumeProject.sort_order",
    )
    experience: Mapped["ResumeExperience"] = relationship(back_populates="client_rows")

    @property
    def projects(self) -> list["ResumeProject"]:
        """プロジェクトを期間の降順でソートして返す。"""
        return sort_by_period_desc(list(self.project_rows))


class ResumeProject(Base):
    __tablename__ = "resume_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resume_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    start_date_value: Mapped[date] = mapped_column("start_date", Date, nullable=False)
    end_date_value: Mapped[date | None] = mapped_column("end_date", Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    challenge: Mapped[str] = mapped_column(Text, nullable=False, default="")
    action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    team_total: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    team_member_rows: Mapped[list["ResumeProjectTeamMember"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ResumeProjectTeamMember.sort_order",
    )
    technology_stack_rows: Mapped[list["ResumeProjectTechnologyStack"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ResumeProjectTechnologyStack.sort_order",
    )
    phase_rows: Mapped[list["ResumeProjectPhase"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ResumeProjectPhase.sort_order",
    )
    client: Mapped["ResumeClient"] = relationship(back_populates="project_rows")

    @property
    def start_date(self) -> str:
        return format_year_month(self.start_date_value) or ""

    @property
    def end_date(self) -> str:
        """DB の end_date が NULL（参画中）の場合は "" を返す（schema 契約と一致）。"""
        return format_year_month(self.end_date_value) or ""

    @property
    def team(self) -> dict:
        return {
            "total": self.team_total,
            "members": list(self.team_member_rows),
        }

    @property
    def technology_stacks(self) -> list["ResumeProjectTechnologyStack"]:
        return list(self.technology_stack_rows)

    @property
    def phases(self) -> list[str]:
        return [phase.name for phase in self.phase_rows]


class ResumeProjectTeamMember(Base):
    __tablename__ = "resume_project_team_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resume_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role: Mapped[str] = mapped_column(String(60), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    project: Mapped["ResumeProject"] = relationship(back_populates="team_member_rows")


class ResumeProjectTechnologyStack(Base):
    __tablename__ = "resume_project_technology_stacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resume_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    project: Mapped["ResumeProject"] = relationship(back_populates="technology_stack_rows")


class ResumeProjectPhase(Base):
    __tablename__ = "resume_project_phases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resume_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    project: Mapped["ResumeProject"] = relationship(back_populates="phase_rows")
