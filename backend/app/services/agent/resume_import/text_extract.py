"""PDF 経歴書のテキスト抽出（決定論ロジック / ADR-0024）。

テキスト埋め込み PDF を pypdf で抽出し、スキャン PDF（テキスト非埋め込み）を判定して
明示的なエラーで倒す（旧設計の空文字握りつぶしの再発防止 / ADR-0004→0008→0024）。
本モジュールは LLM を呼ばず DB にも触れない純粋な前処理。
"""

import logging
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PyPdfError

logger = logging.getLogger(__name__)

# PDF のマジックバイト（先頭）。multipart で送られた任意バイト列の一次弾き。
_PDF_MAGIC = b"%PDF-"

# 正規化後にこの文字数未満なら「テキスト非埋め込み（スキャン相当）」と判定する。
# 氏名だけの表紙でも数十字は出るため、実質空を弾く緩い閾値。
MIN_TEXT_LENGTH = 50


class PdfExtractionError(Exception):
    """PDF として読めない（非 PDF・破損）。router で 422 にマップする。"""


class ScannedPdfError(Exception):
    """テキストが埋め込まれていない（スキャン画像 PDF）。router で 422 にマップする。"""


def looks_like_pdf(data: bytes) -> bool:
    """先頭バイトが PDF マジック（``%PDF-``）かを判定する（一次バリデーション）。"""
    return data[: len(_PDF_MAGIC)] == _PDF_MAGIC


def normalize_text(text: str) -> str:
    """抽出テキストを正規化する。

    - 各行の行末空白を除去する
    - 連続する空行を 1 行に圧縮する（PDF 抽出で頻出する過剰な空行を畳む）
    - 先頭・末尾の空白/空行を除去する
    """
    normalized_lines: list[str] = []
    previous_blank = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line == "":
            if not previous_blank:
                normalized_lines.append("")
            previous_blank = True
        else:
            normalized_lines.append(line)
            previous_blank = False
    return "\n".join(normalized_lines).strip()


def has_sufficient_text(text: str) -> bool:
    """抽出テキストが構造化抽出に足る量かを判定する（スキャン PDF 判定の中核）。"""
    return len(text.strip()) >= MIN_TEXT_LENGTH


def extract_pdf_text(data: bytes) -> str:
    """PDF バイト列から本文テキストを抽出して正規化して返す。

    Raises:
        PdfExtractionError: 非 PDF・破損で読めない。
        ScannedPdfError: 読めたがテキストが埋め込まれていない（スキャン相当）。
    """
    if not looks_like_pdf(data):
        raise PdfExtractionError("PDF ではないファイルです")

    try:
        reader = PdfReader(BytesIO(data))
        pages_text = [page.extract_text() or "" for page in reader.pages]
    except (PyPdfError, ValueError, OSError, KeyError, RecursionError) as exc:
        # 破損 PDF・構造不正。pypdf は PdfReadError（PyPdfError 派生）だけでなく、
        # 必須キー欠落（KeyError: /Root・/Pages）や深いネスト（RecursionError）を
        # 組み込み例外のまま送出することがあるため、それらも 422 へ倒す（500 漏れ防止）。
        # 個人情報は載せずに型のみログ。
        logger.warning("PDF の読み取りに失敗: %s", type(exc).__name__)
        raise PdfExtractionError("PDF を読み取れませんでした") from exc

    text = normalize_text("\n".join(pages_text))
    if not has_sufficient_text(text):
        raise ScannedPdfError("テキストが埋め込まれていない PDF です")
    return text
