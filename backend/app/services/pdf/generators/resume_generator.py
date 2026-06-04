import re
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

# 画面プレビュー（左右 diff）で除去する PDF 専用フォント定義。url 解決が画面では不要なため。
_FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}")


def _esc(text: str) -> str:
    """HTMLエスケープのショートカット"""
    return _html_escape(str(text))


def _md(text: str) -> str:
    """Markdownテキストを安全にHTMLに変換する"""
    return markdown.markdown(str(text), extensions=["tables"])


def _fp(*segments) -> str:
    """form パス属性（data-fp）の値を組み立てる。

    frontend `utils/careerDiff.ts` の change.path を "." 連結した文字列と一致させる契約。
    例: _fp("experiences", 0, "clients", 1, "projects", 0, "role")
        → "experiences.0.clients.1.projects.0.role"
    左右 diff のハイライト・スクロール先特定に使う。WeasyPrint の PDF 出力には影響しない。
    """
    return ".".join(str(s) for s in segments)


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


def _build_project_html(project, fp: str) -> str:
    """プロジェクト1件分のHTMLを組み立てる（fp = このプロジェクトの data-fp プレフィックス）"""
    # ヘッダー（3行構成: 期間/プロジェクト名、役割、工程）
    name = _a(project, "name")
    periods = _a(project, "periods", [])
    role = _a(project, "role")
    phases = _a(project, "phases", [])

    # 1行目: 期間 ／ プロジェクト名
    line1_parts: list[str] = []
    period_str = _format_periods(periods)
    if period_str:
        line1_parts.append(f'<span data-fp="{fp}.periods">{period_str}</span>')
    if name:
        line1_parts.append(f'<span data-fp="{fp}.name">{_esc(name)}</span>')
    line1 = "　／　".join(line1_parts) if line1_parts else ""

    # 2行目: 役割
    line2 = f'役割：<span data-fp="{fp}.role">{_esc(role)}</span>' if role else ""

    # 3行目: 工程
    line3 = ""
    if phases:
        joined = "／".join(_esc(p) for p in phases)
        line3 = f'工程：<span data-fp="{fp}.phases">{joined}</span>'

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

    # 右カラム: 開発環境（技術スタック）
    stacks = _a(project, "technology_stacks", [])
    grouped = group_stacks_by_category(stacks)
    right_parts: list[str] = []
    for cat, names in grouped.items():
        label = _CATEGORY_LABELS.get(cat, cat)
        right_parts.append(
            f"<strong>【{_esc(label)}】</strong><br/>" f"{_esc(', '.join(names))}",
        )
    right_content = "<br/>".join(right_parts) if right_parts else "-"

    # 体制（後方互換: 旧 scale → team の正規化は shared に集約）
    team = normalize_team(project)
    team_parts: list[str] = []
    if team:
        total = _a(team, "total")
        if total:
            team_parts.append(f"{_esc(total)}名")
        members = _a(team, "members", [])
        member_strs = [
            f"{_esc(_a(m, 'role'))}:{_a(m, 'count', 0)}" for m in members if _a(m, "role")
        ]
        if member_strs:
            team_parts.append(" / ".join(member_strs))
    team_text = "<br/>".join(team_parts) if team_parts else "-"

    return (
        f'<div class="project" data-unit="{fp}">{header_html}'
        f'<table class="project-table">'
        f"<tr><th>業務内容</th><th>開発環境</th><th>体制</th></tr>"
        f'<tr><td class="desc" data-fp="{fp}.description">{left_content}</td>'
        f'<td class="env" data-fp="{fp}.technology_stacks">{right_content}</td>'
        f'<td class="team" data-fp="{fp}.team">{team_text}</td></tr>'
        f"</table></div>"
    )


def _build_vacation_html(client, fp: str) -> str:
    """休暇エントリ1件分のHTMLを組み立てる（期間 + 詳細）。fp = この取引先の data-fp プレフィックス。"""
    period = _format_period(
        _a(client, "vacation_start_date"),
        _a(client, "vacation_end_date", ""),
        _a(client, "vacation_is_current", False),
    )
    header = f"休暇　{_esc(period)}" if period else "休暇"
    description = _a(client, "vacation_description")
    body = _md(description) if description else "-"
    return (
        f'<div class="vacation" data-unit="{fp}">'
        f'<div class="vacation-header" data-fp="{fp}.vacation_start_date">{header}</div>'
        f'<div class="vacation-body" data-fp="{fp}.vacation_description">{body}</div>'
        f"</div>"
    )


def _build_html(resume: dict) -> str:
    """職務経歴書データからHTML文字列を組み立てる。

    各値ノードに data-fp（form パス）属性を付与する。これは左右 diff プレビューでの
    変更ハイライト/スクロール先特定に使われる。PDF 生成では無視される（レイアウト不変）。
    """
    parts: list[str] = []

    # タイトル
    parts.append("<h1>職 務 経 歴 書</h1>")

    # 氏名
    full_name = resume.get("full_name") or ""
    parts.append(
        f'<div class="meta">氏名　<span data-fp="full_name">{_esc(full_name)}</span></div>',
    )

    # 記載日（日本時間）
    today = datetime.now(JST)
    parts.append(
        f'<div class="meta">記載日　{today.year}年{today.month}月{today.day}日</div>',
    )

    # 職務要約
    parts.append("<h2>■職務要約</h2>")
    career_summary = resume.get("career_summary", "")
    parts.append(
        '<div class="body-text" data-unit="career_summary" data-fp="career_summary">'
        f"{_md(career_summary)}</div>",
    )

    # 職務経歴
    parts.append("<h2>■職務経歴</h2>")
    experiences = resume.get("experiences", [])
    if not experiences:
        parts.append("<p>-</p>")
    else:
        for i, exp in enumerate(experiences):
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
            info_parts = [
                f'事業内容：<span data-fp="experiences.{i}.business_description">{biz}</span>',
            ]
            if capital:
                info_parts.append(
                    f'資本金：<span data-fp="experiences.{i}.capital">{capital}</span>',
                )
            if emp:
                info_parts.append(
                    f'従業員数：<span data-fp="experiences.{i}.employee_count">{emp}</span>',
                )

            parts.append(f'<div class="company" data-unit="experiences.{i}">')
            parts.append(
                '<div class="company-header">'
                f'<span data-fp="experiences.{i}.start_date">{period}</span>　'
                f'<span data-fp="experiences.{i}.company">{company}</span></div>',
            )
            parts.append(
                f'<div class="company-info">' f'{"　".join(info_parts)}</div>',
            )
            parts.append('<div class="company-body">')

            if not _a(exp, "is_it_company", True):
                # 非IT企業: 取引先/プロジェクトの代わりに詳細を表示
                detail = _a(exp, "description")
                parts.append(
                    f'<div class="company-detail" data-fp="experiences.{i}.description">'
                    f"{_md(detail)}</div>"
                    if detail
                    else "<p>-</p>",
                )
            else:
                # 取引先 → プロジェクト（後方互換含む正規化は shared に集約）
                clients = normalize_clients(exp)
                for j, client in enumerate(clients):
                    client_fp = f"experiences.{i}.clients.{j}"
                    if _a(client, "is_vacation", False):
                        parts.append(_build_vacation_html(client, client_fp))
                        continue
                    client_name = _a(client, "name")
                    if client_name:
                        parts.append(
                            '<div class="client-name">取引先名：'
                            f'<span data-fp="{client_fp}.name">{_esc(client_name)}</span></div>',
                        )
                    projects = _a(client, "projects", [])
                    for k, proj in enumerate(projects):
                        parts.append(_build_project_html(proj, f"{client_fp}.projects.{k}"))

            parts.append("</div></div>")

    # 資格
    parts.append("<h2>■資格</h2>")
    qualifications = resume.get("qualifications", [])
    if not qualifications:
        parts.append("<p>-</p>")
    else:
        parts.append('<table class="qual-table">')
        for i, q in enumerate(qualifications):
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
            parts.append(
                f'<tr data-unit="qualifications.{i}">'
                f'<td><span data-fp="qualifications.{i}.name">{name}</span></td>'
                f'<td><span data-fp="qualifications.{i}.acquired_date">{ds}</span></td></tr>',
            )
        parts.append("</table>")

    # 自己PR
    parts.append("<h2>■自己PR</h2>")
    self_pr = resume.get("self_pr", "")
    parts.append(
        '<div class="body-text" data-unit="self_pr" data-fp="self_pr">' f"{_md(self_pr)}</div>",
    )

    return "\n".join(parts)


def _load_css(for_screen: bool) -> str:
    """resume.css を読み込む。

    for_screen=True（左右 diff プレビュー）: PDF 用フォント(@font-face)を除去し、
    body の font-family フォールバック（sans-serif）に任せる。
    for_screen=False（PDF 生成）: {{ font_path }} を実フォントの URI に置換する。
    """
    css_text = _CSS_PATH.read_text(encoding="utf-8")
    if for_screen:
        return _FONT_FACE_RE.sub("", css_text)
    return css_text.replace("{{ font_path }}", _FONT_PATH.as_uri())


def build_resume_preview(resume: dict) -> tuple[str, str]:
    """保存前プレビュー（左右 diff）用に (body HTML, 画面用 CSS) を返す。

    HTML は data-fp 付き（`_build_html`）。CSS は PDF 専用フォントを除いた画面表示版。
    frontend は両者を iframe srcdoc に流し込んで baseline / 編集中を並べて描画する。
    """
    return _build_html(resume), _load_css(for_screen=True)


def build_resume_pdf(resume: dict) -> bytes:
    """職務経歴書データからPDFバイト列を生成する"""
    html_body = _build_html(resume)

    # CSSテンプレートを読み込み、フォントパスを埋め込む
    css_text = _load_css(for_screen=False)

    full_html = (
        "<!DOCTYPE html>"
        '<html lang="ja"><head>'
        '<meta charset="utf-8">'
        f"<style>{css_text}</style>"
        f"</head><body>{html_body}</body></html>"
    )

    pdf_bytes = weasyprint.HTML(string=full_html).write_pdf()
    return pdf_bytes
