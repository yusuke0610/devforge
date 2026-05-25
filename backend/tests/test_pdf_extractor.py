"""pdf_extractor のテキスト抽出（特に表対応）の検証。

日本語の職務経歴書はグリッド表で在籍期間・従業員数/資本金・体制人数を持つことが多い。
``extract_text()`` だけだと表がフラット化されてラベルと値の対応が崩れるため、
``extract_tables()`` 由来の Markdown 表が末尾に追記されることを確認する。
"""

import io

from app.services.resume_import.pdf_extractor import extract_blocks, extract_text


def _make_table_pdf() -> bytes:
    """グリッド線付きの表を含む PDF を生成する（pdfplumber が表として検出できる）。"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    table = Table(
        [
            ["EmployeeCount", "120"],
            ["Capital", "5000"],
            ["Period", "2020/04-2022/03"],
            ["Team", "8"],
        ]
    )
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    doc.build([Paragraph("Resume Sample", styles["Normal"]), table])
    return buf.getvalue()


def _make_scan_pdf() -> bytes:
    """テキストレイヤーを持たない（描画なしの）PDF を生成する。"""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_extract_text_appends_table_markdown_with_label_value_adjacency() -> None:
    """表のラベルと値が同一 Markdown 行に隣接して復元されること。"""
    result = extract_text(_make_table_pdf())

    assert result.has_text_layer is True
    assert "## 表データ" in result.text
    # フラット化では崩れがちなラベル↔値の隣接が、表データ側で 1 行に復元される
    lines = result.text.splitlines()
    assert any("EmployeeCount" in ln and "120" in ln for ln in lines)
    assert any("Capital" in ln and "5000" in ln for ln in lines)
    assert any("Period" in ln and "2020/04-2022/03" in ln for ln in lines)


def test_extract_text_marks_scan_pdf_without_text_layer() -> None:
    """テキスト希薄な PDF は has_text_layer=False となること。"""
    result = extract_text(_make_scan_pdf())

    assert result.has_text_layer is False


def test_extract_blocks_returns_line_and_table_blocks() -> None:
    """本文行ブロックと表セルブロックの両方が得られること。"""
    result = extract_blocks(_make_table_pdf())

    assert result.has_text_layer is True
    texts = [b.text for b in result.blocks]
    kinds = {b.kind for b in result.blocks}
    # 表セルが個別ブロックになっている（クリックで値だけ流し込める）
    assert "EmployeeCount" in texts
    assert "120" in texts
    assert "table" in kinds
    # 本文（段落）も行ブロックになっている
    assert any("Resume Sample" in t for t in texts)
    assert "line" in kinds


def test_extract_blocks_dedupes_identical_text() -> None:
    """完全一致するブロックは重複排除されること。"""
    result = extract_blocks(_make_table_pdf())
    texts = [b.text for b in result.blocks]
    assert len(texts) == len(set(texts))


def test_extract_blocks_marks_scan_pdf() -> None:
    """テキスト希薄な PDF は has_text_layer=False となること。"""
    result = extract_blocks(_make_scan_pdf())
    assert result.has_text_layer is False
