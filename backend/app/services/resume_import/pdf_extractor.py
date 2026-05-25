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


@dataclass
class ExtractedBlock:
    """インポート補助 UI に並べる「割り当て候補」ブロック。

    kind は本文行 ("line") か表セル ("table")。意味づけ（どの項目か）は行わず、
    構造的に切り出すだけ。ユーザーが UI でクリックして各フィールドへ流し込む。
    """

    kind: str
    text: str


@dataclass
class ExtractedBlocks:
    blocks: list[ExtractedBlock]
    page_count: int
    has_text_layer: bool


def extract_blocks(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> ExtractedBlocks:
    """PDF を「割り当て候補ブロック」の列に分解する（LLM 不使用・決定的）。

    本文は行単位、表はセル単位でブロック化し、完全一致する重複は除外する。
    スキャン PDF（テキストレイヤーなし）は has_text_layer=False を返す。
    """
    import pdfplumber

    blocks: list[ExtractedBlock] = []
    seen: set[str] = set()

    def _add(kind: str, raw: str) -> None:
        # 表セルはセル内改行を空白に潰し、本文行は前後空白のみ除去する
        text = " ".join(raw.split()) if kind == "table" else raw.strip()
        if not text or text in seen:
            return
        seen.add(text)
        blocks.append(ExtractedBlock(kind=kind, text=text))

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages = pdf.pages[:max_pages]
        page_count = len(pdf.pages)
        sparse_pages = 0

        for page in pages:
            page_text = page.extract_text() or ""
            if len(page_text.strip()) < _MIN_CHARS_PER_PAGE:
                sparse_pages += 1
            for line in page_text.split("\n"):
                _add("line", line)
            try:
                tables = page.extract_tables()
            except Exception:
                logger.warning("ページの表抽出に失敗しました (無視)", exc_info=True)
                tables = []
            for table in tables:
                for row in table:
                    for cell in row:
                        if cell:
                            _add("table", str(cell))

        has_text_layer = sparse_pages < max(1, len(pages) / 2) if pages else False

    logger.info(
        "PDF ブロック抽出完了",
        extra={"page_count": page_count, "has_text_layer": has_text_layer},
    )
    return ExtractedBlocks(
        blocks=blocks,
        page_count=page_count,
        has_text_layer=has_text_layer,
    )


def _normalize_cell(value) -> str:
    """表セルの値を 1 行文字列に正規化する（None は空文字、セル内改行は空白に潰す）。"""
    if value is None:
        return ""
    return " ".join(str(value).split())


def _render_tables(page) -> str:
    """ページ内の表を Markdown 表として描画する。

    日本語の職務経歴書は在籍期間・会社概要（従業員数/資本金）・体制（要員）などを
    グリッド表で持つことが多い。``extract_text()`` は表をフラット化してラベルと値の
    対応関係を壊すため、``extract_tables()`` の結果を別途 Markdown 表として残し、
    LLM が「ラベル → 値」を読み取れるようにする。
    """
    try:
        tables = page.extract_tables()
    except Exception:
        # 表抽出は補助的処理。失敗してもテキスト抽出本体は継続させる。
        logger.warning("ページの表抽出に失敗しました (無視)", exc_info=True)
        return ""

    rendered: list[str] = []
    for table in tables:
        rows = [
            "| " + " | ".join(_normalize_cell(c) for c in row) + " |"
            for row in table
            if any(_normalize_cell(c) for c in row)
        ]
        if rows:
            rendered.append("\n".join(rows))

    if not rendered:
        return ""
    return "## 表データ\n" + "\n\n".join(rendered)


def extract_text(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> ExtractedText:
    """PDF バイト列からテキストを抽出する。

    本文テキストに加えて、各ページの表を Markdown 表として末尾に追記する
    （在籍期間・従業員数/資本金・体制人数などのラベル↔値の対応を保つため）。
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
            segments: list[str] = []
            sparse_pages = 0
            for page in pages:
                page_text = page.extract_text() or ""
                # スキャン判定は本文テキストの実文字数で行う（表追記前に評価する）
                if len(page_text.strip()) < _MIN_CHARS_PER_PAGE:
                    sparse_pages += 1
                segments.append(page_text)

                tables_md = _render_tables(page)
                if tables_md:
                    segments.append(tables_md)

            full_text = "\n".join(s for s in segments if s.strip()).strip()
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
