from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..utils.pdf_utils import (
    FONT_NAME,
    HEADER_BG,
    MARGIN,
    PAGE_W,
    TABLE_BORDER,
    escape,
    register_font,
    styles,
)


def _add_page_number(canvas_obj, doc):
    register_font()
    canvas_obj.saveState()
    canvas_obj.setFont(FONT_NAME, 8)
    canvas_obj.drawCentredString(PAGE_W / 2, 10 * mm, f"{canvas_obj.getPageNumber()}")
    canvas_obj.restoreState()


def _table_style(
    header_range: tuple[tuple[int, int], tuple[int, int]],
    valign: str,
) -> TableStyle:
    """グリッド・ヘッダ背景・パディングをまとめた共通 TableStyle を返す。"""
    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
            ("BACKGROUND", header_range[0], header_range[1], HEADER_BG),
            ("VALIGN", (0, 0), (-1, -1), valign),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def build_intelligence_pdf(payload: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    s = styles()
    elements = []
    content_width = PAGE_W - 2 * MARGIN

    # Title
    elements.append(Paragraph("GitHub 連携レポート", s["title"]))
    elements.append(Spacer(1, 2 * mm))

    # Overview
    username = escape(payload.get("username", ""))
    repos = payload.get("repos_analyzed", 0)
    skills_count = payload.get("unique_skills", 0)
    analyzed_at = escape(payload.get("analyzed_at", ""))

    overview_data = [
        [Paragraph("<b>ユーザー</b>", s["body"]), Paragraph(username, s["body"])],
        [
            Paragraph("<b>対象リポジトリ数</b>", s["body"]),
            Paragraph(str(repos), s["body"]),
        ],
        [
            Paragraph("<b>ユニークスキル数</b>", s["body"]),
            Paragraph(str(skills_count), s["body"]),
        ],
        [Paragraph("<b>取得日時</b>", s["body"]), Paragraph(analyzed_at, s["body"])],
    ]
    overview_table = Table(overview_data, colWidths=[40 * mm, content_width - 40 * mm])
    overview_table.setStyle(_table_style(((0, 0), (0, -1)), "MIDDLE"))
    elements.append(overview_table)
    elements.append(Spacer(1, 4 * mm))

    # AI Summary
    summary = payload.get("summary", "")
    if summary:
        elements.append(Paragraph("■ AI要約", s["section_header"]))
        elements.append(Paragraph(escape(summary).replace("\n", "<br/>"), s["body"]))
        elements.append(Spacer(1, 3 * mm))

    # Career Prediction
    prediction = payload.get("prediction", {})
    if prediction:
        elements.append(Paragraph("■ キャリア予測", s["section_header"]))

        current = prediction.get("current_role", {})
        if current:
            role_name = escape(current.get("role_name", ""))
            conf = current.get("confidence", 0)
            matching = ", ".join(current.get("matching_skills", []))

            elements.append(
                Paragraph(
                    f"<b>現在のロール:</b> {role_name} (確信度: {conf:.0%})",
                    s["body"],
                )
            )
            if matching:
                elements.append(
                    Paragraph(
                        f"<b>マッチするスキル:</b> {escape(matching)}",
                        s["body_small"],
                    )
                )
            elements.append(Spacer(1, 2 * mm))

        next_roles = prediction.get("next_roles", [])
        if next_roles:
            elements.append(Paragraph("<b>次のキャリアステップ</b>", s["body"]))
            role_data = [
                [
                    Paragraph("<b>ロール</b>", s["body_small"]),
                    Paragraph("<b>確信度</b>", s["body_small"]),
                    Paragraph("<b>不足スキル</b>", s["body_small"]),
                ]
            ]
            for role in next_roles:
                conf = role.get("confidence", 0)
                missing = ", ".join(role.get("missing_skills", []))
                role_data.append(
                    [
                        Paragraph(escape(role.get("role_name", "")), s["body_small"]),
                        Paragraph(f"{conf:.0%}", s["body_small"]),
                        Paragraph(escape(missing) if missing else "-", s["body_small"]),
                    ]
                )
            role_table = Table(role_data, colWidths=[45 * mm, 20 * mm, content_width - 65 * mm])
            role_table.setStyle(_table_style(((0, 0), (-1, 0)), "TOP"))
            elements.append(role_table)
            elements.append(Spacer(1, 2 * mm))

        long_term = prediction.get("long_term_roles", [])
        if long_term:
            elements.append(Paragraph("<b>長期キャリア候補</b>", s["body"]))
            for role in long_term:
                conf = role.get("confidence", 0)
                elements.append(
                    Paragraph(
                        f"・{escape(role.get('role_name', ''))} ({conf:.0%})",
                        s["body_small"],
                    )
                )
            elements.append(Spacer(1, 2 * mm))

    # Career Simulation
    simulation = payload.get("simulation", {})
    paths = simulation.get("paths", [])
    if paths:
        elements.append(Paragraph("■ キャリアパスシミュレーション", s["section_header"]))
        for i, p in enumerate(paths, 1):
            path_str = " → ".join(p.get("path", []))
            conf = p.get("confidence", 0)
            elements.append(
                Paragraph(
                    f"{i}. {escape(path_str)} (確信度: {conf:.0%})",
                    s["body"],
                )
            )
            desc = p.get("description", "")
            if desc:
                elements.append(Paragraph(f"　{escape(desc)}", s["body_small"]))
        elements.append(Spacer(1, 3 * mm))

    doc.build(elements, onFirstPage=_add_page_number, onLaterPages=_add_page_number)
    buffer.seek(0)
    return buffer.getvalue()
