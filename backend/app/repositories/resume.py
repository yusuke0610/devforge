from sqlalchemy.orm import selectinload

from ..core.date_utils import parse_year_month
from ..models import (
    Resume,
    ResumeClient,
    ResumeExperience,
    ResumeProject,
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
            client_rows=[
                self._build_client_row(client_index, client)
                for client_index, client in enumerate(payload.get("clients", []))
            ],
        )

    def _build_client_row(self, index: int, payload: dict[str, object]) -> ResumeClient:
        sorted_projects = sort_by_period_desc(
            payload.get("projects", []),
            start_key="start_date",
            end_key="end_date",
        )
        return ResumeClient(
            sort_order=index,
            name=payload.get("name", ""),
            has_client=payload.get("has_client", True),
            project_rows=[
                self._build_project_row(project_index, project)
                for project_index, project in enumerate(sorted_projects)
            ],
        )

    def _build_project_row(self, index: int, payload: dict[str, object]) -> ResumeProject:
        team = payload.get("team", {})
        return ResumeProject(
            sort_order=index,
            name=payload.get("name", ""),
            start_date_value=parse_year_month(payload["start_date"]),
            end_date_value=(
                parse_year_month(payload["end_date"]) if payload.get("end_date") else None
            ),
            is_current=payload.get("is_current", False),
            role=payload.get("role", ""),
            challenge=payload.get("challenge", ""),
            action=payload.get("action", ""),
            result=payload.get("result", ""),
            team_total=team.get("total", ""),
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
