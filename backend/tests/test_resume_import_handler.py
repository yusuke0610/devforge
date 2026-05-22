"""ResumeImportHandler の単体テスト。LLM はモック化し、DB は実 SQLite セッションを使用。"""

import asyncio
import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from app.models.resume_import import ResumeImport
from app.services.tasks.exceptions import NonRetryableError
from app.services.tasks.handlers.resume_import import ResumeImportHandler


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_minimal_pdf() -> bytes:
    """テキストレイヤーを持つ最小限の PDF バイト列を生成する。"""
    import reportlab.lib.pagesizes as ps
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=ps.A4)
    c.drawString(72, 720, "山田 太郎")
    c.drawString(72, 700, "職務経歴書")
    c.drawString(72, 680, "バックエンドエンジニアとして5年の経験があります。")
    c.save()
    return buf.getvalue()


def _make_scan_pdf() -> bytes:
    """テキストなし（スキャン相当）の PDF バイト列を生成する。"""
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.save()
    return buf.getvalue()


def _create_import_record(db_session, user_id: str, pdf_bytes: bytes) -> ResumeImport:
    record = ResumeImport(
        user_id=user_id,
        pdf_blob=pdf_bytes,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture()
def test_user(db_session):
    from app.repositories import UserRepository

    repo = UserRepository(db_session)
    if not repo.get_by_username("handler-test-user"):
        repo.create("handler-test-user", hashed_password=None, email="handler-test@example.com")
    return repo.get_by_username("handler-test-user")


# ── 正常系 ──────────────────────────────────────────────────────────────────


def test_run_success(db_session, test_user):
    """正常な職務経歴書 PDF → status=completed / result_json が保存される。"""
    pdf_bytes = _make_minimal_pdf()
    record = _create_import_record(db_session, test_user.id, pdf_bytes)

    mock_llm = AsyncMock()
    judge_response = json.dumps({"is_resume": True, "confidence": 0.9, "reason": "職歴が記載されている"})
    extract_response = json.dumps({
        "full_name": "山田 太郎",
        "career_summary": "バックエンドエンジニア",
        "self_pr": "API 設計が得意",
        "experiences": [],
        "qualifications": [],
    })
    mock_llm.generate = AsyncMock(side_effect=[judge_response, extract_response])

    handler = ResumeImportHandler()
    with patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm):
        _run(handler.run(db_session, {"user_id": test_user.id, "import_id": record.id}))

    db_session.refresh(record)
    assert record.status == "completed"
    assert record.result_json is not None
    result = json.loads(record.result_json)
    assert result["full_name"] == "山田 太郎"
    assert record.pdf_blob is None
    assert record.is_resume_flag is True


# ── 異常系: スキャン PDF ──────────────────────────────────────────────────


def test_run_scan_pdf_raises_non_retryable(db_session, test_user):
    """テキストレイヤーのない PDF → NonRetryableError / error_code が RESUME_IMPORT_INVALID。"""
    pdf_bytes = _make_scan_pdf()
    record = _create_import_record(db_session, test_user.id, pdf_bytes)

    handler = ResumeImportHandler()

    # pdfplumber のテキストレイヤー判定はファイル依存で揺れるため、抽出結果を直接モックする
    from app.services.resume_import.pdf_extractor import ExtractedText

    scan_result = ExtractedText(text="", page_count=1, has_text_layer=False)
    with patch(
        "app.services.resume_import.pdf_extractor.extract_text",
        return_value=scan_result,
    ):
        with pytest.raises(NonRetryableError, match="スキャン PDF"):
            _run(handler.run(db_session, {"user_id": test_user.id, "import_id": record.id}))

    db_session.refresh(record)
    assert record.error_message is not None
    assert "スキャン PDF" in record.error_message
    assert record.pdf_blob is None

    from app.core.errors import resolve_async_error_code

    assert resolve_async_error_code(record.error_message) == "RESUME_IMPORT_INVALID"


# ── 異常系: 職務経歴書でない ──────────────────────────────────────────────


def test_run_not_a_resume_raises_non_retryable(db_session, test_user):
    """LLM が職務経歴書でないと判定 → NonRetryableError / error_code が RESUME_IMPORT_NOT_A_RESUME。"""
    pdf_bytes = _make_minimal_pdf()
    record = _create_import_record(db_session, test_user.id, pdf_bytes)

    mock_llm = AsyncMock()
    judge_response = json.dumps({"is_resume": False, "confidence": 0.1, "reason": "請求書です"})
    mock_llm.generate = AsyncMock(return_value=judge_response)

    handler = ResumeImportHandler()
    with patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm):
        with pytest.raises(NonRetryableError, match="not_a_resume"):
            _run(handler.run(db_session, {"user_id": test_user.id, "import_id": record.id}))

    db_session.refresh(record)
    assert record.is_resume_flag is False
    assert "not_a_resume" in record.error_message
    assert record.pdf_blob is None

    from app.core.errors import resolve_async_error_code

    assert resolve_async_error_code(record.error_message) == "RESUME_IMPORT_NOT_A_RESUME"


# ── 異常系: ペイロード不正 ───────────────────────────────────────────────


def test_run_missing_payload_raises_non_retryable(db_session):
    """必須キー欠落 → NonRetryableError。"""
    handler = ResumeImportHandler()
    with pytest.raises(NonRetryableError, match="必須キー"):
        _run(handler.run(db_session, {}))


# ── get_record ───────────────────────────────────────────────────────────


def test_get_record_returns_record(db_session, test_user):
    """get_record が正しいレコードを返すこと。"""
    record = ResumeImport(
        user_id=test_user.id,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)

    handler = ResumeImportHandler()
    found = handler.get_record(db_session, {"user_id": test_user.id, "import_id": record.id})
    assert found is not None
    assert found.id == record.id


def test_get_record_returns_none_for_missing(db_session, test_user):
    """存在しない import_id → None を返す。"""
    handler = ResumeImportHandler()
    result = handler.get_record(db_session, {"user_id": test_user.id, "import_id": "nonexistent-id"})
    assert result is None
