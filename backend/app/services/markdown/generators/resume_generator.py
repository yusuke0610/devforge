from typing import Any

from ...shared.resume_format import (
    CATEGORY_LABELS,
    group_stacks_by_category,
    normalize_clients,
    normalize_team,
)
from ...shared.resume_format import attr as _a
from ..templates import resume_template as tpl
from ..utils.markdown_utils import field_line, format_period


def build_resume_markdown(payload: dict[str, Any]) -> str:
    """
    Builds a Japanese resume as a single Markdown-formatted string from the provided payload.
    
    The payload may include keys such as:
    - full_name: applicant's full name
    - qualifications: list of {name, acquired_date}
    - career_summary: free-form career summary text
    - experiences: list of experience objects; each experience may contain company, start_date, end_date, is_current, business_description, employee_count, capital, and normalized client/project data (projects include project-level fields, team, phases, technology_stacks)
    - self_pr: free-form self-promotion text
    
    Returns:
        A single string containing the resume formatted in Markdown (Japanese labels and section structure).
    """
    lines: list[str] = []
    lines.append(tpl.TITLE)
    lines.append("")

    full_name = payload.get("full_name", "")
    if full_name:
        lines.append(field_line("氏名", full_name))
    lines.append("")

    qualifications = payload.get("qualifications", [])
    if qualifications:
        lines.append(tpl.SECTION_QUALIFICATIONS)
        lines.append("")
        for q in qualifications:
            name = _a(q, "name")
            date = _a(q, "acquired_date")
            lines.append(f"- {name} ({date}取得)")
        lines.append("")

    career_summary = payload.get("career_summary", "")
    if career_summary:
        lines.append(tpl.SECTION_CAREER_SUMMARY)
        lines.append("")
        lines.append(career_summary)
        lines.append("")

    experiences = payload.get("experiences", [])
    if experiences:
        lines.append(tpl.SECTION_EXPERIENCES)
        lines.append("")
        for exp in experiences:
            company = _a(exp, "company")
            start = _a(exp, "start_date")
            end = _a(exp, "end_date")
            is_current = _a(exp, "is_current", False)
            period = format_period(start, end, is_current)
            lines.append(f"### {company}")
            lines.append("")
            lines.append(field_line("期間", period))
            biz = _a(exp, "business_description")
            if biz:
                lines.append(field_line("事業内容", biz))
            emp = _a(exp, "employee_count")
            if emp:
                lines.append(field_line("従業員数", f"{emp}名"))
            cap = _a(exp, "capital")
            if cap:
                lines.append(field_line("資本金", f"{cap}千万円"))
            lines.append("")

            # clients → projects（後方互換含む正規化は shared に集約）
            clients = normalize_clients(exp)
            for client in clients:
                client_name = _a(client, "name")
                if client_name:
                    lines.append(f"#### {client_name}")
                    lines.append("")
                projects = _a(client, "projects", [])
                for proj in projects:
                    name = _a(proj, "name")
                    if name:
                        lines.append(f"##### {name}")
                        lines.append("")
                    proj_start = _a(proj, "start_date")
                    proj_end = _a(proj, "end_date")
                    proj_is_current = _a(proj, "is_current", False)
                    if proj_start:
                        proj_period = format_period(proj_start, proj_end, proj_is_current)
                        lines.append(field_line("期間", proj_period))
                    role = _a(proj, "role")
                    if role:
                        lines.append(field_line("担当", role))
                    challenge = _a(proj, "challenge")
                    if challenge:
                        lines.append(field_line("課題", challenge))
                    action = _a(proj, "action")
                    if action:
                        lines.append(field_line("行動", action))
                    result = _a(proj, "result")
                    if result:
                        lines.append(field_line("成果", result))
                    # 体制（後方互換: 旧 scale → team の正規化は shared に集約）
                    team = normalize_team(proj)
                    if team:
                        total = _a(team, "total")
                        members = _a(team, "members", [])
                        member_strs = [
                            f"{_a(m, 'role')}:{_a(m, 'count', 0)}"
                            for m in members
                            if _a(m, "role")
                        ]
                        team_text = f"{total}名" if total else ""
                        if member_strs:
                            sep = "（" if team_text else ""
                            end = "）" if team_text else ""
                            team_text += f"{sep}{' / '.join(member_strs)}{end}"
                        if team_text:
                            lines.append(field_line("体制", team_text))
                    phases = _a(proj, "phases", [])
                    if phases:
                        lines.append(field_line("工程", ", ".join(phases)))
                    stacks = _a(proj, "technology_stacks", [])
                    if stacks:
                        grouped = group_stacks_by_category(stacks)
                        parts = [
                            f"{CATEGORY_LABELS.get(c, c)}: {', '.join(ns)}"
                            for c, ns in grouped.items()
                        ]
                        lines.append(field_line("技術スタック", " / ".join(parts)))
                    lines.append("")

    self_pr = payload.get("self_pr", "")
    if self_pr:
        lines.append(tpl.SECTION_SELF_PR)
        lines.append("")
        lines.append(self_pr)
        lines.append("")

    return "\n".join(lines)
