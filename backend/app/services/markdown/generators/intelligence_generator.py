from typing import Any

from ..templates import intelligence_template as tpl
from ..utils.markdown_utils import field_line


def build_intelligence_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(tpl.TITLE)
    lines.append("")

    # Overview
    lines.append(tpl.SECTION_OVERVIEW)
    lines.append("")
    lines.append(field_line("ユーザー", payload.get("username", "")))
    lines.append(field_line("対象リポジトリ数", str(payload.get("repos_analyzed", 0))))
    lines.append(field_line("ユニークスキル数", str(payload.get("unique_skills", 0))))
    lines.append(field_line("取得日時", payload.get("analyzed_at", "")))
    lines.append("")

    # AI Summary
    summary = payload.get("summary", "")
    if summary:
        lines.append(tpl.SECTION_AI_SUMMARY)
        lines.append("")
        lines.append(summary)
        lines.append("")

    # Career Prediction
    prediction = payload.get("prediction", {})
    if prediction:
        lines.append(tpl.SECTION_CAREER_PREDICTION)
        lines.append("")

        current = prediction.get("current_role", {})
        if current:
            role_name = current.get("role_name", "")
            conf = current.get("confidence", 0)
            lines.append(f"### 現在のロール: {role_name} ({conf:.0%})")
            lines.append("")
            matching = current.get("matching_skills", [])
            if matching:
                lines.append(field_line("マッチするスキル", ", ".join(matching)))
            missing = current.get("missing_skills", [])
            if missing:
                lines.append(field_line("不足スキル", ", ".join(missing)))
            lines.append("")

        next_roles = prediction.get("next_roles", [])
        if next_roles:
            lines.append("### 次のキャリアステップ")
            lines.append("")
            for role in next_roles:
                conf = role.get("confidence", 0)
                lines.append(f"- **{role.get('role_name', '')}** ({conf:.0%})")
                missing = role.get("missing_skills", [])
                if missing:
                    lines.append(f"  - 不足スキル: {', '.join(missing)}")
            lines.append("")

        long_term = prediction.get("long_term_roles", [])
        if long_term:
            lines.append("### 長期キャリア候補")
            lines.append("")
            for role in long_term:
                conf = role.get("confidence", 0)
                lines.append(f"- **{role.get('role_name', '')}** ({conf:.0%})")
            lines.append("")

    # Career Simulation
    simulation = payload.get("simulation", {})
    paths = simulation.get("paths", [])
    if paths:
        lines.append(tpl.SECTION_CAREER_SIMULATION)
        lines.append("")
        for i, p in enumerate(paths, 1):
            path_str = " -> ".join(p.get("path", []))
            conf = p.get("confidence", 0)
            lines.append(f"{i}. {path_str} ({conf:.0%})")
            desc = p.get("description", "")
            if desc:
                lines.append(f"   {desc}")
        lines.append("")

    return "\n".join(lines)
