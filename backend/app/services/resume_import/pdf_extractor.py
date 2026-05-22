"""pdfplumber を使った PDF テキスト抽出ユーティリティ。"""

import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 1ページあたりのテキスト文字数がこの値未満のページが全体の半数以上ならスキャン PDF とみなす
_MIN_CHARS_PER_PAGE = 30
MAX_PAGES = 20


@dataclass
class ExtractedText:
    text: str
    page_count: int
    has_text_layer: bool


def extract_text(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> ExtractedText:
    """PDF バイト列からテキストを抽出する。

    スキャン PDF（テキストレイヤーなし）の場合は has_text_layer=False を返す。
    max_pages を超えるページは無視する。
    """
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages[:max_pages]
        page_count = len(pdf.pages)

        if not pages:
            full_text = ""
            has_text_layer = False
        else:
            texts: list[str] = []
            sparse_pages = 0
            for page in pages:
                page_text = page.extract_text() or ""
                texts.append(page_text)
                if len(page_text.strip()) < _MIN_CHARS_PER_PAGE:
                    sparse_pages += 1

            full_text = "\n".join(texts).strip()
            # 半数以上のページがテキスト希薄ならスキャン PDF と判定
            has_text_layer = sparse_pages < max(1, len(pages) / 2)

        logger.info(
            "PDF テキスト抽出完了",
            extra={
                "page_count": page_count,
                "extracted_pages": len(pages),
                "has_text_layer": has_text_layer,
                "char_count": len(full_text),
            },
        )
        return ExtractedText(
            text=full_text,
            page_count=page_count,
            has_text_layer=has_text_layer,
        )
