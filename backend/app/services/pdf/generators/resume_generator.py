from datetime import datetime
from html import escape as _html_escape
from pathlib import Path

import markdown
import weasyprint

from ....core.date_utils import JST
from ...shared.resume_format import CATEGORY_LABELS as _CATEGORY_LABELS
from ...shared.resume_format import (
    attr as _a,
)
from ...shared.resume_format import (
    group_stacks_by_category,
    normalize_clients,
    normalize_team,
)

_CSS_PATH = Path(__file__).resolve().parent.parent / "templates" / "resume.css"
_FONT_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "fonts" / "NotoSansJP-Regular.ttf"
)


def _esc(text: str) -> str:
    """HTMLエスケープのショートカット"""
    return _html_escape(str(text))


def _md(text: str) -> str:
    """Markdownテキストを安全にHTMLに変換する"""
    return markdown.markdown(str(text), extensions=["tables"])


def _format_period(start: str, end: str, is_current: bool) -> str:
    """1 期間をフォーマットする。在籍中は end を "" で受ける契約（Experience 用）。"""
    s = start.replace("-", " 年 ") + " 月" if "-" in start else start
    if is_current:
        return f"{s}〜現在"
    e = end.replace("-", " 年 ") + " 月" if "-" in end else end
    return f"{s}〜{e}"


def _format_periods(periods: list) -> str:
    """複数期間を「、」区切りで連結してフォーマットする（Project 用）。"""
    parts: list[str] = []
    for p in periods:
        start = _a(p, "start_date")
        if not start:
            continue
        end = _a(p, "end_date", "")
        is_current = _a(p, "is_current", False)
        parts.append(_format_period(start, end, is_current))
    return "、".join(parts)


def _format_team(project) -> str:
    """体制の人数情報を「6名（PM：1名、SE：6名）」形式の1行文字列にする。

    後方互換（旧 scale → team）の正規化は shared に集約。情報が無ければ空文字を返す。
    """
    team = normalize_team(project)
    if not team:
        return ""
    total = _a(team, "total")
    total_text = f"{_esc(total)}名" if total else ""
    members = _a(team, "members", [])
    member_strs = [
        f"{_esc(_a(m, 'role'))}：{_esc(_a(m, 'count', 0))}名" for m in members if _a(m, "role")
    ]
    member_text = f"（{'、'.join(member_strs)}）" if member_strs else ""
    return f"{total_text}{member_text}"


def _build_project_html(project) -> str:
    """プロジェクト1件分のHTMLを組み立てる"""
    # ヘッダー（3行構成: 期間/プロジェクト名、役割、工程）
    name = _a(project, "name")
    periods = _a(project, "periods", [])
    role = _a(project, "role")
    phases = _a(project, "phases", [])

    # 1行目: 期間 ／ プロジェクト名
    line1_parts: list[str] = []
    period_str = _format_periods(periods)
    if period_str:
        line1_parts.append(period_str)
    if name:
        line1_parts.append(_esc(name))
    line1 = "　／　".join(line1_parts) if line1_parts else ""

    # 2行目: 役割（体制の人数情報を「、体制：…」として役割の右側に併記する）
    team_text = _format_team(project)
    role_part = f"役割：{_esc(role)}" if role else ""
    team_part = f"体制：{team_text}" if team_text else ""
    line2 = "、".join(p for p in [role_part, team_part] if p)

    # 3行目: 工程
    line3 = ""
    if phases:
        line3 = f"工程：{'／'.join(_esc(p) for p in phases)}"

    header_lines = [ln for ln in [line1, line2, line3] if ln]
    header_html = ""
    if header_lines:
        header_html = '<div class="project-header">' + "<br/>".join(header_lines) + "</div>"

    # 左カラム: 業務内容
    left_parts: list[str] = []
    description = _a(project, "description")
    if description:
        left_parts.append(_md(description))
    left_content = "".join(left_parts) if left_parts else "-"

    # 右カラム: スキルセット（技術スタックのカテゴリ別表示）
    stacks = _a(project, "technology_stacks", [])
    grouped = group_stacks_by_category(stacks)
    right_parts: list[str] = []
    for cat, names in grouped.items():
        label = _CATEGORY_LABELS.get(cat, cat)
        right_parts.append(
            f"<strong>【{_esc(label)}】</strong><br/>" f"{_esc(', '.join(names))}",
        )
    right_content = "<br/>".join(right_parts) if right_parts else "-"

    # 体制は表のカラムではなく役割行に併記する（line2 で処理済み）。
    return (
        f'<div class="project">{header_html}'
        f'<table class="project-table">'
        f"<thead><tr><th>業務内容</th><th>スキルセット</th></tr></thead>"
        f'<tbody><tr><td class="desc">{left_content}</td>'
        f'<td class="env">{right_content}</td></tr></tbody>'
        f"</table></div>"
    )


def _build_vacation_html(client) -> str:
    """休暇エントリ1件分のHTMLを組み立てる（期間 + 詳細）。"""
    period = _format_period(
        _a(client, "vacation_start_date"),
        _a(client, "vacation_end_date", ""),
        _a(client, "vacation_is_current", False),
    )
    header = f"休暇　{_esc(period)}" if period else "休暇"
    description = _a(client, "vacation_description")
    body = _md(description) if description else "-"
    return (
        f'<div class="vacation">'
        f'<div class="vacation-header">{header}</div>'
        f'<div class="vacation-body">{body}</div>'
        f"</div>"
    )


def _build_html(resume: dict) -> str:
    """職務経歴書データからHTML文字列を組み立てる"""
    parts: list[str] = []

    # タイトル
    parts.append("<h1>職 務 経 歴 書</h1>")

    # 氏名
    full_name = resume.get("full_name") or ""
    parts.append(
        f'<div class="meta">氏名　{_esc(full_name)}</div>',
    )

    # 記載日（日本時間）
    today = datetime.now(JST)
    parts.append(
        f'<div class="meta">記載日　{today.year}年{today.month}月{today.day}日</div>',
    )

    # 職務要約
    parts.append("<h2>■職務要約</h2>")
    career_summary = resume.get("career_summary", "")
    parts.append(f'<div class="body-text">{_md(career_summary)}</div>')

    # 職務経歴
    parts.append("<h2>■職務経歴</h2>")
    experiences = resume.get("experiences", [])
    if not experiences:
        parts.append("<p>-</p>")
    else:
        for exp in experiences:
            period = _format_period(
                _a(exp, "start_date"),
                _a(exp, "end_date", ""),
                _a(exp, "is_current", False),
            )
            company = _esc(_a(exp, "company"))

            biz = _esc(
                _a(exp, "business_description") or _a(exp, "title"),
            )
            capital_raw = _a(exp, "capital")
            emp_raw = _a(exp, "employee_count")
            capital_unit = _a(exp, "capital_unit", "千万円")
            capital = f"{_esc(capital_raw)}{_esc(capital_unit)}" if capital_raw else ""
            emp = f"{_esc(emp_raw)}名" if emp_raw else ""
            info_parts = [f"事業内容：{biz}"]
            if capital:
                info_parts.append(f"資本金：{capital}")
            if emp:
                info_parts.append(f"従業員数：{emp}")

            parts.append('<div class="company">')
            parts.append(
                f'<div class="company-header">' f"{period}　{company}</div>",
            )
            parts.append(
                f'<div class="company-info">' f'{"　".join(info_parts)}</div>',
            )
            parts.append('<div class="company-body">')

            if not _a(exp, "is_it_company", True):
                # 非IT企業: 取引先/プロジェクトの代わりに詳細を表示
                detail = _a(exp, "description")
                parts.append(
                    f'<div class="company-detail">{_md(detail)}</div>' if detail else "<p>-</p>",
                )
            else:
                # 取引先 → プロジェクト（後方互換含む正規化は shared に集約）
                clients = normalize_clients(exp)
                for client in clients:
                    if _a(client, "is_vacation", False):
                        parts.append(_build_vacation_html(client))
                        continue
                    client_name = _a(client, "name")
                    if client_name:
                        parts.append(
                            f'<div class="client-name">' f"案件名：{_esc(client_name)}</div>",
                        )
                    projects = _a(client, "projects", [])
                    for proj in projects:
                        parts.append(_build_project_html(proj))

            parts.append("</div></div>")

    # 資格
    parts.append("<h2>■資格</h2>")
    qualifications = resume.get("qualifications", [])
    if not qualifications:
        parts.append("<p>-</p>")
    else:
        parts.append('<table class="qual-table">')
        for q in qualifications:
            name = _esc(_a(q, "name"))
            raw_date = _a(q, "acquired_date")
            if raw_date and "-" in raw_date:
                dp = raw_date.split("-")
                if len(dp) == 3:
                    ds = f"{dp[0]}年{dp[1].lstrip('0')}月" f"{dp[2].lstrip('0')}日取得"
                elif len(dp) == 2:
                    ds = f"{dp[0]}年{dp[1].lstrip('0')}月取得"
                else:
                    ds = f"{_esc(raw_date)}取得"
            else:
                ds = f"{_esc(raw_date)}取得" if raw_date else ""
            parts.append(f"<tr><td>{name}</td><td>{ds}</td></tr>")
        parts.append("</table>")

    # 自己PR
    parts.append("<h2>■自己PR</h2>")
    self_pr = resume.get("self_pr", "")
    parts.append(f'<div class="body-text">{_md(self_pr)}</div>')

    return "\n".join(parts)


def build_resume_pdf(resume: dict) -> bytes:
    """職務経歴書データからPDFバイト列を生成する"""
    html_body = _build_html(resume)

    # CSSテンプレートを読み込み、フォントパスを埋め込む
    css_text = _CSS_PATH.read_text(encoding="utf-8")
    css_text = css_text.replace(
        "{{ font_path }}",
        _FONT_PATH.as_uri(),
    )

    full_html = (
        "<!DOCTYPE html>"
        '<html lang="ja"><head>'
        '<meta charset="utf-8">'
        f"<style>{css_text}</style>"
        f"</head><body>{html_body}</body></html>"
    )

    pdf_bytes = weasyprint.HTML(string=full_html).write_pdf()
    return pdf_bytes
