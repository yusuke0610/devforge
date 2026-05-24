"""resume_imports ルーターの統合テスト。"""

import io
import json

import reportlab.lib.pagesizes as ps
from fastapi.testclient import TestClient
from httpx import Response
from reportlab.pdfgen import canvas

from conftest import auth_header


def _make_pdf_bytes(text: str = "山田 太郎\n職務経歴書\nバックエンドエンジニア") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=ps.A4)
    for i, line in enumerate(text.split("\n")):
        c.drawString(72, 720 - i * 20, line)
    c.save()
    return buf.getvalue()


def _upload_pdf(client: TestClient, headers: dict[str, str], pdf_bytes: bytes) -> Response:
    resp = client.post(
        "/api/resumes/import",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        headers=headers,
    )
    return resp


# ── POST /api/resumes/import ─────────────────────────────────────────────


def test_start_import_returns_202_with_import_id(client: TestClient) -> None:
    """正常な PDF アップロード → 202 で import_id が返る。"""
    headers = auth_header(client, "import-test-user-1")
    pdf_bytes = _make_pdf_bytes()

    resp = _upload_pdf(client, headers, pdf_bytes)
    assert resp.status_code == 202
    data = resp.json()
    assert "import_id" in data
    assert len(data["import_id"]) > 0


def test_start_import_rejects_non_pdf(client: TestClient) -> None:
    """PDF 以外のファイル → 422 / RESUME_IMPORT_INVALID。"""
    headers = auth_header(client, "import-test-user-2")
    resp = client.post(
        "/api/resumes/import",
        files={"file": ("resume.txt", b"not a pdf", "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "RESUME_IMPORT_INVALID"


def test_start_import_rejects_oversized_file(client: TestClient) -> None:
    """10 MB 超過 → 422 / RESUME_IMPORT_INVALID。"""
    headers = auth_header(client, "import-test-user-3")
    oversized = b"%PDF-1.4 " + b"x" * (11 * 1024 * 1024)
    resp = client.post(
        "/api/resumes/import",
        files={"file": ("big.pdf", oversized, "application/pdf")},
        headers=headers,
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "RESUME_IMPORT_INVALID"


def test_start_import_requires_auth(client: TestClient) -> None:
    """認証なし → 401。"""
    pdf_bytes = _make_pdf_bytes()
    resp = client.post(
        "/api/resumes/import",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 401


# ── GET /api/resumes/import/{id}/status ─────────────────────────────────


def test_get_status_returns_pending(client: TestClient) -> None:
    """作成直後は status=pending が返る。"""
    headers = auth_header(client, "import-status-user-1")
    pdf_bytes = _make_pdf_bytes()

    resp = _upload_pdf(client, headers, pdf_bytes)
    assert resp.status_code == 202
    import_id = resp.json()["import_id"]

    status_resp = client.get(f"/api/resumes/import/{import_id}/status", headers=headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["status"] in ("pending", "processing")


def test_get_status_returns_404_for_unknown(client: TestClient) -> None:
    """存在しない import_id → 404。"""
    headers = auth_header(client, "import-status-user-2")
    resp = client.get("/api/resumes/import/nonexistent-id/status", headers=headers)
    assert resp.status_code == 404


def test_get_status_user_isolation(client: TestClient, db_session) -> None:
    """他ユーザーのレコードは取得できない（404）。"""
    from datetime import datetime, timedelta, timezone

    from app.models.resume_import import ResumeImport
    from app.repositories import UserRepository

    # user A のレコードを DB に直接作成する（セッション切り替えを避けるため）
    repo = UserRepository(db_session)
    if not repo.get_by_username("import-isolation-a"):
        repo.create("import-isolation-a", hashed_password=None, email="import-isolation-a@example.com")
    user_a = repo.get_by_username("import-isolation-a")

    record = ResumeImport(
        user_id=user_a.id,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    import_id = record.id

    # user B として認証し、user A のレコードを取得 → 404
    headers_b = auth_header(client, "import-isolation-b")
    status_resp = client.get(f"/api/resumes/import/{import_id}/status", headers=headers_b)
    assert status_resp.status_code == 404


# ── GET /api/resumes/import/{id}/result ─────────────────────────────────


def test_get_result_returns_409_while_pending(client: TestClient) -> None:
    """pending 状態での result 取得 → 409。"""
    headers = auth_header(client, "import-result-user-1")
    pdf_bytes = _make_pdf_bytes()

    resp = _upload_pdf(client, headers, pdf_bytes)
    import_id = resp.json()["import_id"]

    result_resp = client.get(f"/api/resumes/import/{import_id}/result", headers=headers)
    assert result_resp.status_code == 409


def test_get_result_returns_200_when_completed(client: TestClient, db_session) -> None:
    """completed レコードの result 取得 → 200 / result が返る。"""
    headers = auth_header(client, "import-result-user-2")
    pdf_bytes = _make_pdf_bytes()

    resp = _upload_pdf(client, headers, pdf_bytes)
    import_id = resp.json()["import_id"]

    # DB 上で直接 completed に更新する
    from app.models.resume_import import ResumeImport

    record = db_session.query(ResumeImport).filter_by(id=import_id).first()
    record.status = "completed"
    record.is_resume_flag = True
    record.result_json = json.dumps({
        "full_name": "山田 太郎",
        "career_summary": "バックエンドエンジニア",
        "self_pr": "API 設計が得意",
        "experiences": [],
        "qualifications": [],
    })
    db_session.commit()

    result_resp = client.get(f"/api/resumes/import/{import_id}/result", headers=headers)
    assert result_resp.status_code == 200
    data = result_resp.json()
    assert data["result"]["full_name"] == "山田 太郎"
    assert data["is_resume"] is True


# ── GET /api/resumes/import/{id}/progress ───────────────────────────────


def test_get_progress_returns_default_when_no_redis_data(client: TestClient) -> None:
    """Redis にデータが無い場合は step_index=0 / total_steps=3 のデフォルトが返る。"""
    headers = auth_header(client, "import-progress-user-1")
    pdf_bytes = _make_pdf_bytes()

    resp = _upload_pdf(client, headers, pdf_bytes)
    import_id = resp.json()["import_id"]

    progress_resp = client.get(f"/api/resumes/import/{import_id}/progress", headers=headers)
    assert progress_resp.status_code == 200
    data = progress_resp.json()
    assert data["task_id"] == import_id
    # Redis 未書き込みのデフォルト（resume_import は 3 ステップ）
    assert data["step_index"] == 0
    assert data["total_steps"] == 3
    assert data["step_label"] is None


def test_get_progress_returns_404_for_unknown(client: TestClient) -> None:
    """存在しない import_id → 404。"""
    headers = auth_header(client, "import-progress-user-2")
    resp = client.get("/api/resumes/import/nonexistent-id/progress", headers=headers)
    assert resp.status_code == 404


def test_get_progress_user_isolation(client: TestClient, db_session) -> None:
    """他ユーザーのレコードの progress は取得できない（404）。"""
    from datetime import datetime, timedelta, timezone

    from app.models.resume_import import ResumeImport
    from app.repositories import UserRepository

    repo = UserRepository(db_session)
    if not repo.get_by_username("import-progress-isolation-a"):
        repo.create(
            "import-progress-isolation-a",
            hashed_password=None,
            email="import-progress-isolation-a@example.com",
        )
    user_a = repo.get_by_username("import-progress-isolation-a")

    record = ResumeImport(
        user_id=user_a.id,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    import_id = record.id

    headers_b = auth_header(client, "import-progress-isolation-b")
    progress_resp = client.get(f"/api/resumes/import/{import_id}/progress", headers=headers_b)
    assert progress_resp.status_code == 404
