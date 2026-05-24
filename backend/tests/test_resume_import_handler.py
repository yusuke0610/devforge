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


def test_run_success(db_session, session_factory, test_user):
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
        _run(handler.run(session_factory, {"user_id": test_user.id, "import_id": record.id}))

    db_session.expire_all()
    db_session.refresh(record)
    assert record.status == "completed"
    assert record.result_json is not None
    result = json.loads(record.result_json)
    assert result["full_name"] == "山田 太郎"
    assert record.pdf_blob is None
    assert record.is_resume_flag is True


# ── 回帰: LLM が null を返しても result_json から ResumeBase が再構成できる ──


def test_run_llm_null_output_is_sanitized(db_session, session_factory, test_user):
    """LLM が schema 違反の null を返しても、result_json はサニタイズ済みで保存される。

    過去発生: completed として保存されたが /result 取得時に Pydantic
    ValidationError で 500 を返す（ghost completion）状態の再発防止。
    """
    from app.schemas.resume import ResumeBase

    pdf_bytes = _make_minimal_pdf()
    record = _create_import_record(db_session, test_user.id, pdf_bytes)

    judge_response = json.dumps({"is_resume": True, "confidence": 0.9, "reason": "OK"})
    # 実ログで観測された null パターンを再現
    extract_response = json.dumps({
        "full_name": "山田 太郎",
        "career_summary": "BE エンジニア",
        "self_pr": "PR",
        "experiences": [
            {
                "company": "会社A",
                "business_description": "SaaS",
                "start_date": "2020-04",
                "end_date": "2022-03",
                "is_current": False,
                "employee_count": "100名",
                "capital": "1億円",
                "clients": [
                    {
                        "name": None,
                        "has_client": False,
                        "projects": [
                            {
                                "name": "P1",
                                "start_date": "2020-04",
                                "end_date": "2022-03",
                                "is_current": False,
                                "role": "BE",
                                "description": "API",
                                "challenge": None,
                                "action": None,
                                "result": None,
                            }
                        ],
                    }
                ],
            }
        ],
        "qualifications": [],
    })
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(side_effect=[judge_response, extract_response])

    handler = ResumeImportHandler()
    with patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm):
        _run(handler.run(session_factory, {"user_id": test_user.id, "import_id": record.id}))

    db_session.expire_all()
    db_session.refresh(record)
    assert record.status == "completed"
    # /result エンドポイントと同じ経路: json.loads → ResumeBase(**parsed)
    parsed = json.loads(record.result_json)
    resume = ResumeBase(**parsed)
    proj = resume.experiences[0].clients[0].projects[0]
    assert proj.challenge == ""
    assert proj.action == ""
    assert proj.result == ""
    assert resume.experiences[0].clients[0].name == ""


# ── 異常系: スキャン PDF ──────────────────────────────────────────────────


def test_run_scan_pdf_raises_non_retryable(db_session, session_factory, test_user):
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
            _run(handler.run(session_factory, {"user_id": test_user.id, "import_id": record.id}))

    db_session.expire_all()
    db_session.refresh(record)
    assert record.error_message is not None
    assert "スキャン PDF" in record.error_message
    assert record.pdf_blob is None

    from app.core.errors import resolve_async_error_code

    assert resolve_async_error_code(record.error_message) == "RESUME_IMPORT_INVALID"


# ── 異常系: 職務経歴書でない ──────────────────────────────────────────────


def test_run_not_a_resume_raises_non_retryable(db_session, session_factory, test_user):
    """LLM が職務経歴書でないと判定 → NonRetryableError / error_code が RESUME_IMPORT_NOT_A_RESUME。"""
    pdf_bytes = _make_minimal_pdf()
    record = _create_import_record(db_session, test_user.id, pdf_bytes)

    mock_llm = AsyncMock()
    judge_response = json.dumps({"is_resume": False, "confidence": 0.1, "reason": "請求書です"})
    mock_llm.generate = AsyncMock(return_value=judge_response)

    handler = ResumeImportHandler()
    with patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm):
        with pytest.raises(NonRetryableError, match="not_a_resume"):
            _run(handler.run(session_factory, {"user_id": test_user.id, "import_id": record.id}))

    db_session.expire_all()
    db_session.refresh(record)
    assert record.is_resume_flag is False
    assert record.error_message is not None
    assert "not_a_resume" in record.error_message
    assert record.pdf_blob is None

    from app.core.errors import resolve_async_error_code

    assert resolve_async_error_code(record.error_message) == "RESUME_IMPORT_NOT_A_RESUME"


# ── 異常系: ペイロード不正 ───────────────────────────────────────────────


def test_run_missing_payload_raises_non_retryable(session_factory):
    """必須キー欠落 → NonRetryableError。"""
    handler = ResumeImportHandler()
    with pytest.raises(NonRetryableError, match="必須キー"):
        _run(handler.run(session_factory, {}))


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


# ── 進捗バー: set_progress が 4 回（3 ステップ + 完了）呼ばれること ────────


def test_run_emits_progress_steps(db_session, session_factory, test_user):
    """正常系で set_progress が steps 1/2/3 と 完了 の計 4 回呼ばれる。

    フロントの TaskProgressStepper でバーが伸びるための前提条件。
    """
    pdf_bytes = _make_minimal_pdf()
    record = _create_import_record(db_session, test_user.id, pdf_bytes)

    mock_llm = AsyncMock()
    judge_response = json.dumps({"is_resume": True, "confidence": 0.9, "reason": "OK"})
    extract_response = json.dumps({
        "full_name": "山田 太郎",
        "career_summary": "",
        "self_pr": "",
        "experiences": [],
        "qualifications": [],
    })
    mock_llm.generate = AsyncMock(side_effect=[judge_response, extract_response])

    handler = ResumeImportHandler()
    with patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm), patch(
        "app.services.tasks.handlers.resume_import.set_progress",
        new_callable=AsyncMock,
    ) as mock_progress:
        _run(handler.run(session_factory, {"user_id": test_user.id, "import_id": record.id}))

    # 呼び出し順: (1, 3, "PDFテキスト抽出中...") → (2, 3, "職務経歴書か判定中...")
    #              → (3, 3, "構造化抽出中...") → (3, 3, "完了")
    assert mock_progress.await_count == 4
    calls = [call.args for call in mock_progress.await_args_list]
    # task_id は import_id（user_id ではなく）
    assert all(args[0] == record.id for args in calls)
    # step_index / total_steps / label
    assert (calls[0][1], calls[0][2]) == (1, 3)
    assert "PDFテキスト抽出中" in calls[0][3]
    assert (calls[1][1], calls[1][2]) == (2, 3)
    assert "判定中" in calls[1][3]
    assert (calls[2][1], calls[2][2]) == (3, 3)
    assert "構造化抽出中" in calls[2][3]
    assert (calls[3][1], calls[3][2]) == (3, 3)
    assert "完了" in calls[3][3]


# ── libSQL stream 失効回避: LLM 中はハンドラ側のセッションが閉じている ────


def test_no_handler_session_during_llm_call(db_session, session_factory, test_user):
    """LLM 呼び出し中にハンドラが DB セッションを保持していないこと。

    libSQL (Hrana over HTTP) の stream は idle で失効するため、LLM の長時間待機
    中にハンドラ側のセッションが開いたままだと最終 commit が STREAM_EXPIRED で
    落ちる（実際に blog_summarize で発生した）。本テストはフェーズ分離が機能し、
    LLM 呼び出し時点で session_factory から払い出されたセッションがすべて
    close 済みであることを検証する。
    """
    pdf_bytes = _make_minimal_pdf()
    record = _create_import_record(db_session, test_user.id, pdf_bytes)

    # session_factory が払い出した全セッションを追跡する
    issued_sessions = []
    original_factory = session_factory

    def tracking_factory():
        s = original_factory()
        issued_sessions.append(s)
        return s

    active_sessions_during_llm: list[int] = []

    async def fake_generate(*_args, **_kwargs):
        # LLM 呼び出し時点で、ハンドラが open 中のセッション数を記録する。
        # close 後の session は is_active=False になる（SQLAlchemy 2.0）。
        active = sum(1 for s in issued_sessions if s.is_active and s.in_transaction())
        active_sessions_during_llm.append(active)
        await asyncio.sleep(0.01)
        return json.dumps({
            "is_resume": True,
            "confidence": 0.9,
            "reason": "職歴記載",
            "full_name": "山田 太郎",
            "career_summary": "",
            "self_pr": "",
            "experiences": [],
            "qualifications": [],
        })

    mock_llm = AsyncMock()
    mock_llm.generate = fake_generate

    handler = ResumeImportHandler()
    with patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm):
        _run(handler.run(tracking_factory, {"user_id": test_user.id, "import_id": record.id}))

    assert active_sessions_during_llm, "fake_generate が一度も呼ばれていません"
    assert not any(active_sessions_during_llm), (
        "LLM 呼び出し中にハンドラがアクティブなトランザクションを保持していました。"
        " libSQL では idle 接続の stream が失効するため、LLM 前後でセッションを"
        f" 必ず開閉すること。active 履歴: {active_sessions_during_llm}"
    )
