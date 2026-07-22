"""PDF テキスト抽出（決定論ロジック）の単体テスト（ADR-0024 / #527）。

TDD 対象（`app/services/agent/resume_import/text_extract.py`）。純関数
（正規化・十分性判定・PDF 判定）と、pypdf を使うテキスト抽出の両方を検証する。
実 PDF は WeasyPrint（生成専用・テスト環境で利用可）で作る。
"""

import pytest
from app.services.agent.resume_import.text_extract import (
    PdfExtractionError,
    ScannedPdfError,
    extract_pdf_text,
    has_sufficient_text,
    looks_like_pdf,
    normalize_text,
)
from weasyprint import HTML


def _make_pdf(body_html: str) -> bytes:
    """テキスト埋め込み PDF を生成する（抽出可能な本文を持つ）。"""
    pdf = HTML(string=f"<html><body>{body_html}</body></html>").write_pdf()
    assert pdf is not None  # target 未指定の write_pdf は bytes を返す
    return pdf


# ---- looks_like_pdf ----


def test_looks_like_pdf_accepts_pdf_magic() -> None:
    assert looks_like_pdf(b"%PDF-1.7\n...") is True


def test_looks_like_pdf_rejects_non_pdf() -> None:
    assert looks_like_pdf(b"PK\x03\x04zip") is False
    assert looks_like_pdf(b"") is False
    assert looks_like_pdf(b"%PD") is False


# ---- normalize_text ----


def test_normalize_text_strips_trailing_whitespace_per_line() -> None:
    assert normalize_text("abc   \n  def  ") == "abc\n  def"


def test_normalize_text_collapses_consecutive_blank_lines() -> None:
    assert normalize_text("a\n\n\n\nb") == "a\n\nb"


def test_normalize_text_trims_leading_and_trailing_blanks() -> None:
    assert normalize_text("\n\n  content  \n\n") == "content"


# ---- has_sufficient_text ----


def test_has_sufficient_text_true_for_long_text() -> None:
    assert has_sufficient_text("あ" * 100) is True


def test_has_sufficient_text_false_for_empty_or_short() -> None:
    assert has_sufficient_text("") is False
    assert has_sufficient_text("   \n  ") is False
    assert has_sufficient_text("短い") is False


# ---- extract_pdf_text ----


def test_extract_pdf_text_returns_embedded_text() -> None:
    """テキスト埋め込み PDF から本文テキストを抽出する。

    テスト環境のフォントに日本語グリフが無く（WeasyPrint が .notdef で描画し pypdf が
    抽出できない）ため、抽出機構自体の検証は ASCII 本文で行う（抽出できるか否かが論点）。
    """
    pdf = _make_pdf(
        "<p>Career summary: backend engineer with five years of experience.</p>"
        "<p>Self PR: focused on maintainable and well-tested system design.</p>"
    )
    text = extract_pdf_text(pdf)
    assert "Career summary" in text
    assert "backend engineer" in text


def test_extract_pdf_text_rejects_non_pdf_bytes() -> None:
    """PDF でないバイト列は PdfExtractionError。"""
    with pytest.raises(PdfExtractionError):
        extract_pdf_text(b"this is not a pdf")


def test_extract_pdf_text_rejects_corrupt_pdf() -> None:
    """マジックバイトはあるが壊れた PDF は PdfExtractionError。"""
    with pytest.raises(PdfExtractionError):
        extract_pdf_text(b"%PDF-1.7\nbroken garbage not a real pdf structure")


def test_extract_pdf_text_raises_scanned_for_textless_pdf() -> None:
    """テキストがほぼ無い PDF（スキャン相当）は ScannedPdfError。"""
    pdf = _make_pdf("<p>&nbsp;</p>")
    with pytest.raises(ScannedPdfError):
        extract_pdf_text(pdf)


@pytest.mark.parametrize("raised", [KeyError("/Root"), RecursionError()])
def test_extract_pdf_text_wraps_builtin_parser_errors(monkeypatch, raised) -> None:
    """pypdf が組み込み例外（KeyError / RecursionError）を漏らしても PdfExtractionError に倒す。

    マジックバイトは有効だが構造が壊れた PDF で pypdf が PdfReadError 以外を送出しても、
    500 に漏らさず 422（PdfExtractionError）へマップすることを保証する。
    """
    from app.services.agent.resume_import import text_extract

    def _raise(*_args, _exc=raised, **_kwargs):
        raise _exc

    monkeypatch.setattr(text_extract, "PdfReader", _raise)
    with pytest.raises(PdfExtractionError):
        extract_pdf_text(b"%PDF-1.7\n" + b"x" * 100)
