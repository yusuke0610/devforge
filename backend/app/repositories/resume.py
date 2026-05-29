from sqlalchemy.orm import selectinload

from ..core.date_utils import parse_year_month
from ..models import (
    Resume,
    ResumeClient,
    ResumeExperience,
    ResumeProject,
    ResumeProjectPeriod,
    ResumeProjectPhase,
    ResumeProjectTeamMember,
    ResumeProjectTechnologyStack,
    ResumeQualification,
)
from ..services.shared.sort_utils import sort_by_date_asc, sort_by_period_desc
from .base import SingleUserDocumentRepository


class ResumeRepository(SingleUserDocumentRepository):
    _model = Resume
    _loader_options = (
        selectinload(Resume.experience_rows).selectinload(ResumeExperience.client_rows),
        selectinload(Resume.experience_rows)
        .selectinload(ResumeExperience.client_rows)
        .selectinload(ResumeClient.project_rows)
        .selectinload(ResumeProject.period_rows),
        selectinload(Resume.experience_rows)
        .selectinload(ResumeExperience.client_rows)
        .selectinload(ResumeClient.project_rows)
        .selectinload(ResumeProject.team_member_rows),
        selectinload(Resume.experience_rows)
        .selectinload(ResumeExperience.client_rows)
        .selectinload(ResumeClient.project_rows)
        .selectinload(ResumeProject.technology_stack_rows),
        selectinload(Resume.experience_rows)
        .selectinload(ResumeExperience.client_rows)
        .selectinload(ResumeClient.project_rows)
        .selectinload(ResumeProject.phase_rows),
        selectinload(Resume.qualification_rows),
    )

    def _apply_payload(self, entity: Resume, payload: dict[str, object]) -> None:
        entity.full_name = payload["full_name"]
        entity.career_summary = payload["career_summary"]
        entity.self_pr = payload["self_pr"]
        sorted_experiences = sort_by_period_desc(
            payload.get("experiences", []),
            start_key="start_date",
            end_key="end_date",
        )
        entity.experience_rows = [
            self._build_experience_row(index, experience)
            for index, experience in enumerate(sorted_experiences)
        ]
        sorted_qualifications = sort_by_date_asc(
            payload.get("qualifications", []),
            date_key="acquired_date",
        )
        entity.qualification_rows = [
            ResumeQualification(
                sort_order=index,
                acquired_date_value=parse_year_month(item["acquired_date"]),
                name=item["name"],
            )
            for index, item in enumerate(sorted_qualifications)
        ]

    def _build_experience_row(self, index: int, payload: dict[str, object]) -> ResumeExperience:
        return ResumeExperience(
            sort_order=index,
            company=payload["company"],
            business_description=payload["business_description"],
            start_date_value=parse_year_month(payload["start_date"]),
            end_date_value=(
                parse_year_month(payload["end_date"]) if payload.get("end_date") else None
            ),
            is_current=payload.get("is_current", False),
            employee_count=payload.get("employee_count", ""),
            capital=payload.get("capital", ""),
            capital_unit=payload.get("capital_unit", "千万円"),
            is_it_company=payload.get("is_it_company", True),
            description=payload.get("description", ""),
            client_rows=[
                self._build_client_row(client_index, client)
                for client_index, client in enumerate(payload.get("clients", []))
            ],
        )

    def _build_client_row(self, index: int, payload: dict[str, object]) -> ResumeClient:
        projects = list(payload.get("projects", []))
        sorted_projects = sorted(projects, key=self._project_sort_key)
        vacation_start = payload.get("vacation_start_date") or ""
        vacation_end = payload.get("vacation_end_date") or ""
        return ResumeClient(
            sort_order=index,
            name=payload.get("name", ""),
            has_client=payload.get("has_client", True),
            is_vacation=payload.get("is_vacation", False),
            vacation_start_date_value=parse_year_month(vacation_start) if vacation_start else None,
            vacation_end_date_value=parse_year_month(vacation_end) if vacation_end else None,
            vacation_is_current=payload.get("vacation_is_current", False),
            vacation_description=payload.get("vacation_description", ""),
            project_rows=[
                self._build_project_row(project_index, project)
                for project_index, project in enumerate(sorted_projects)
            ],
        )

    @staticmethod
    def _project_sort_key(proj: dict[str, object]) -> tuple:
        """複数期間を持つプロジェクトを sort_by_period_desc と同じ降順ロジックでソートする。"""
        from datetime import date as _date

        def _parse(val: object) -> _date | None:
            if val is None:
                return None
            if isinstance(val, _date):
                return val
            if isinstance(val, str) and val:
                if len(val) == 7 and val[4] == "-":
                    return _date.fromisoformat(f"{val}-01")
                return _date.fromisoformat(val)
            return None

        periods = proj.get("periods", [])
        is_any_current = any(p.get("is_current") for p in periods)
        starts = [_parse(p.get("start_date")) for p in periods]
        effective_start = max((s for s in starts if s), default=_date.min)
        if is_any_current:
            return (0, _date.max - effective_start)
        ends = [_parse(p.get("end_date")) for p in periods if p.get("end_date")]
        effective_end = max(ends, default=_date.min)
        return (1, _date.max - effective_end, _date.max - effective_start)

    def _build_project_row(self, index: int, payload: dict[str, object]) -> ResumeProject:
        team = payload.get("team", {})
        periods = list(payload.get("periods", []))
        return ResumeProject(
            sort_order=index,
            name=payload.get("name", ""),
            role=payload.get("role", ""),
            description=payload.get("description", ""),
            team_total=team.get("total", ""),
            period_rows=[
                ResumeProjectPeriod(
                    sort_order=period_index,
                    start_date_value=parse_year_month(period["start_date"]),
                    end_date_value=(
                        parse_year_month(period["end_date"]) if period.get("end_date") else None
                    ),
                    is_current=period.get("is_current", False),
                )
                for period_index, period in enumerate(periods)
            ],
            team_member_rows=[
                ResumeProjectTeamMember(
                    sort_order=member_index,
                    role=member["role"],
                    count=member["count"],
                )
                for member_index, member in enumerate(team.get("members", []))
            ],
            technology_stack_rows=[
                ResumeProjectTechnologyStack(
                    sort_order=stack_index,
                    category=stack["category"],
                    name=stack["name"],
                )
                for stack_index, stack in enumerate(payload.get("technology_stacks", []))
            ],
            phase_rows=[
                ResumeProjectPhase(sort_order=phase_index, name=phase)
                for phase_index, phase in enumerate(payload.get("phases", []))
            ],
        )
