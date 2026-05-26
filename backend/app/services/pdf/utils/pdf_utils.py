import base64
import logging
import re
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_FONT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fonts"
_FONT_REGISTERED = False
FONT_NAME = "NotoSansJP"


def register_font() -> None:
    """フォントをReportLabに登録します。"""
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return
    font_path = _FONT_DIR / "NotoSansJP-Regular.ttf"
    if font_path.exists():
        pdfmetrics.registerFont(TTFont(FONT_NAME, str(font_path)))
    else:
        raise FileNotFoundError(f"Font not found: {font_path}")
    _FONT_REGISTERED = True


PAGE_W, PAGE_H = A4
MARGIN = 15 * mm

TABLE_BORDER = colors.HexColor("#666666")
HEADER_BG = colors.HexColor("#d6dce8")


def styles() -> dict:
    """PDF生成に使用するスタイルシートを生成します。"""
    register_font()
    base = getSampleStyleSheet()

    s = {}
    s["title"] = ParagraphStyle(
        "title",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=18,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    s["date"] = ParagraphStyle(
        "date",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=10,
        alignment=TA_RIGHT,
    )
    s["name"] = ParagraphStyle(
        "name",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=11,
        alignment=TA_RIGHT,
        spaceAfter=4 * mm,
    )
    s["section_header"] = ParagraphStyle(
        "section_header",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=16,
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    s["body"] = ParagraphStyle(
        "body",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=9,
        leading=14,
        spaceBefore=1 * mm,
    )
    s["body_small"] = ParagraphStyle(
        "body_small",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=8,
        leading=12,
    )
    s["company_header"] = ParagraphStyle(
        "company_header",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        spaceBefore=3 * mm,
        spaceAfter=1 * mm,
    )
    s["project_header"] = ParagraphStyle(
        "project_header",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=9,
        leading=13,
        spaceBefore=2 * mm,
        spaceAfter=1 * mm,
    )
    s["qual"] = ParagraphStyle(
        "qual",
        parent=base["Normal"],
        fontName=FONT_NAME,
        fontSize=9,
        leading=14,
    )
    return s


def escape(text: str) -> str:
    """HTML特殊文字をエスケープします。"""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_period(start_date: str, end_date: str, is_current: bool) -> str:
    """期間（開始〜終了）をフォーマットします。在籍中は end_date を "" で受ける契約。"""
    start = start_date.replace("-", " 年 ") + " 月" if "-" in start_date else start_date
    if is_current:
        return f"{start}〜現在"
    end = end_date.replace("-", " 年 ") + " 月" if "-" in end_date else end_date
    return f"{start}〜{end}"


def parse_date_ym(date_str: str) -> tuple[str, str]:
    """'YYYY-MM' または 'YYYY-MM-DD' を (年, 月) にパースします。"""
    if not date_str or "-" not in date_str:
        return ("", "")
    parts = date_str.split("-")
    year = parts[0]
    month = parts[1].lstrip("0") if len(parts) >= 2 else ""
    return (year, month)


def decode_photo(data_url: str | None) -> BytesIO | None:
    """base64形式のデータURLを BytesIO にデコードします。失敗した場合は None を返します。"""
    if not data_url:
        return None
    try:
        match = re.match(r"data:[^;]+;base64,(.+)", data_url, re.DOTALL)
        if not match:
            return None
        raw = base64.b64decode(match.group(1))
        return BytesIO(raw)
    except Exception:
        logging.warning("Failed to decode photo data URL", exc_info=True)
        return None
