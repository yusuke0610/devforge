"""PDF 経歴書インポート API の統合テスト（ADR-0024 / #527）。

`POST /api/agent/resume-import/pdf` の正常系・非対応 PDF・LLM 失敗・パース失敗・
レート制限・未認証を検証する。LLM はモックし実 API は呼ばない。実 PDF は WeasyPrint
（生成専用・テスト環境で利用可）で作る。DB はモックしない（実 SQLite セッション）。
"""

import json

from app.core import env_keys
from app.services.agent.llm.base import LLMClient, LLMError, LLMResult
from app.services.agent.resume_import import import_service
from fastapi.testclient import TestClient
from weasyprint import HTML

from conftest import auth_header


class _FakeLLM(LLMClient):
    """固定応答 or 例外を返すテスト用 LLM。"""

    def __init__(self, response: str | None = None, error: Exception | None = None):
        self._response = response
        self._error = error

    async def generate(self, system_prompt, messages, output_schema, model_id) -> LLMResult:
        if self._error:
            raise self._error
        assert self._response is not None
        return LLMResult(text=self._response, input_tokens=10, output_tokens=20)


def _mock_llm(monkeypatch, *, response=None, error=None) -> _FakeLLM:
    fake = _FakeLLM(response=response, error=error)
    monkeypatch.setattr(import_service, "get_llm_client", lambda provider: fake)
    return fake


def _import_json(**fields) -> str:
    payload = {
        "full_name": "",
        "career_summary": "",
        "self_pr": "",
        "experiences": [],
    }
    payload.update(fields)
    return json.dumps(payload, ensure_ascii=False)


def _render_pdf(body_html: str) -> bytes:
    """テスト用 PDF を生成する（target 未指定の write_pdf は bytes を返す）。"""
    pdf = HTML(string=f"<html><body>{body_html}</body></html>").write_pdf()
    assert pdf is not None
    return pdf


def _text_pdf() -> bytes:
    """テキスト埋め込み PDF（ASCII 本文で抽出可能にする）。"""
    return _render_pdf(
        "<p>Career summary: backend engineer with five years of experience "
        "building and operating web services.</p>"
        "<p>Self PR: I value maintainability and thorough testing.</p>"
    )


def _upload(client: TestClient, data: bytes, *, filename="resume.pdf", content_type="application/pdf"):
    return client.post(
        "/api/agent/resume-import/pdf",
        files={"file": (filename, data, content_type)},
        headers=auth_header(client),
    )


def test_import_pdf_success_returns_extracted_payload(client: TestClient, monkeypatch) -> None:
    """テキスト埋め込み PDF → 抽出 payload を 200 で返す。"""
    _mock_llm(
        monkeypatch,
        response=_import_json(
            full_name="山田 太郎",
            career_summary="バックエンドエンジニアとして 5 年。",
            self_pr="保守性を重視。",
            experiences=[
                {
                    "company": "株式会社サンプル",
                    "business_description": "受託開発",
                    "start_date": "2020-04",
                    "end_date": "",
                    "description": "API 開発を担当。",
                }
            ],
        ),
    )
    res = _upload(client, _text_pdf())
    assert res.status_code == 200
    body = res.json()
    assert body["full_name"] == "山田 太郎"
    assert body["career_summary"] == "バックエンドエンジニアとして 5 年。"
    assert len(body["experiences"]) == 1
    assert body["experiences"][0]["company"] == "株式会社サンプル"


def test_import_pdf_rejects_non_pdf(client: TestClient, monkeypatch) -> None:
    """PDF でないファイルは抽出段階で 422（import_invalid_pdf）。LLM には到達しない。"""
    _mock_llm(monkeypatch, response=_import_json())
    res = _upload(client, b"this is plain text, not a pdf")
    assert res.status_code == 422
    assert "読み取れませんでした" in res.json()["message"]


def test_import_pdf_rejects_scanned_pdf(client: TestClient, monkeypatch) -> None:
    """テキスト非埋め込み（スキャン相当）PDF は 422（import_scanned_pdf）。"""
    _mock_llm(monkeypatch, response=_import_json())
    res = _upload(client, _render_pdf("<p>&nbsp;</p>"))
    assert res.status_code == 422
    assert "テキストを含む PDF" in res.json()["message"]


def test_import_pdf_llm_failure_returns_502(client: TestClient, monkeypatch) -> None:
    """LLM 呼び出し失敗は 502 AGENT_LLM_ERROR。"""
    _mock_llm(monkeypatch, error=LLMError("boom"))
    res = _upload(client, _text_pdf())
    assert res.status_code == 502
    assert res.json()["code"] == "AGENT_LLM_ERROR"


def test_import_pdf_parse_failure_returns_502(client: TestClient, monkeypatch) -> None:
    """LLM 応答が不正 JSON（リトライ後も失敗）は 502 AGENT_PARSE_ERROR。"""
    _mock_llm(monkeypatch, response="not a json at all")
    res = _upload(client, _text_pdf())
    assert res.status_code == 502
    assert res.json()["code"] == "AGENT_PARSE_ERROR"


def test_import_pdf_daily_rate_limit_returns_429(client: TestClient, monkeypatch) -> None:
    """日次上限到達で 429（LLM 呼び出し前に弾く）。"""
    monkeypatch.setenv(env_keys.AGENT_DAILY_LIMIT, "1")
    _mock_llm(monkeypatch, response=_import_json(full_name="太郎"))
    first = _upload(client, _text_pdf())
    assert first.status_code == 200
    second = _upload(client, _text_pdf())
    assert second.status_code == 429
    assert second.json()["code"] == "AGENT_DAILY_LIMIT_EXCEEDED"


def test_import_pdf_requires_auth(client: TestClient) -> None:
    """未認証は 401。"""
    res = client.post(
        "/api/agent/resume-import/pdf",
        files={"file": ("resume.pdf", _text_pdf(), "application/pdf")},
    )
    assert res.status_code == 401
