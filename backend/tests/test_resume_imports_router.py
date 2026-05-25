"""resume_imports ルーター（同期ブロック抽出）の統合テスト。"""

import io

import reportlab.lib.pagesizes as ps
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from conftest import auth_header


def _make_pdf_bytes(text: str = "Taro Yamada\nAcme Corp Inc\nBackend Engineer") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=ps.A4)
    for i, line in enumerate(text.split("\n")):
        c.drawString(72, 720 - i * 20, line)
    c.save()
    return buf.getvalue()


# ── POST /api/resumes/import/extract（同期・ブロック抽出・LLM 不使用）─────────


def test_extract_blocks_returns_200_with_blocks(client: TestClient) -> None:
    """正常な PDF → 200 で割り当て候補ブロックが返る。"""
    headers = auth_header(client, "import-extract-user-1")
    # reportlab 既定フォント (Helvetica) は日本語を描画できず抽出が空になるため、
    # 「有効 PDF → 200 でブロックが返る」検証は ASCII テキストで行う。
    pdf_bytes = _make_pdf_bytes("Taro Yamada\nAcme Corp Inc\n2020/04 - 2022/03\nBackend Engineer")

    resp = client.post(
        "/api/resumes/import/extract",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 200
    blocks = resp.json()["blocks"]
    assert len(blocks) > 0
    assert {"id", "kind", "text"} <= set(blocks[0].keys())
    texts = [b["text"] for b in blocks]
    assert any("Acme Corp Inc" in t for t in texts)


def test_extract_blocks_rejects_non_pdf(client: TestClient) -> None:
    """PDF 以外 → 422 / RESUME_IMPORT_INVALID。"""
    headers = auth_header(client, "import-extract-user-2")
    resp = client.post(
        "/api/resumes/import/extract",
        files={"file": ("resume.txt", b"not a pdf", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "RESUME_IMPORT_INVALID"


def test_extract_blocks_requires_auth(client: TestClient) -> None:
    """認証なし → 401。"""
    pdf_bytes = _make_pdf_bytes()
    resp = client.post(
        "/api/resumes/import/extract",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 401
