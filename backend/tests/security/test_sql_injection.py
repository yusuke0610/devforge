"""SQL インジェクション検証。
SQLi メタ文字を流しても 500 にならず・他レコードを壊さず・他ユーザーデータを返さない。
"""

from __future__ import annotations

import pytest
from app.models import User
from fastapi.testclient import TestClient

from conftest import auth_header

from ._helpers import RESUME_PAYLOAD, SQLI_PAYLOADS, count_rows


class TestSQLInjection:
    """SQLi メタ文字を流しても 500 にならず・他レコードを壊さず・他ユーザーデータを返さない。"""

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_resume_full_name_treats_payload_as_literal(
        self, client: TestClient, db_session, payload: str
    ) -> None:
        headers = auth_header(client, "sqli-resume")
        resp = client.post(
            "/api/resumes",
            json={**RESUME_PAYLOAD, "full_name": payload},
            headers=headers,
        )
        assert resp.status_code == 201
        latest = client.get("/api/resumes/latest", headers=headers)
        assert latest.status_code == 200
        # ペイロードがリテラルとしてそのまま読み出せること
        assert latest.json()["full_name"] == payload
        # users テーブルが破壊されていないこと（少なくとも 1 行は残る）
        assert count_rows(db_session, User) >= 1

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_resume_path_param_rejects_sqli(
        self, client: TestClient, payload: str
    ) -> None:
        """resume_id は UUID 型なので SQLi 文字列は DB に到達しない。
        UUID 型違反は 422、URL に ``/`` を含むペイロードはルートが一致せず 404 になるが、
        いずれも「攻撃文字列が DB クエリに乗らない」ことを示すので両方を許容する。
        """
        headers = auth_header(client, "sqli-resume-path")
        resp = client.get(f"/api/resumes/{payload}", headers=headers)
        assert resp.status_code in (404, 422), resp.text

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_blog_account_path_returns_404_for_sqli(
        self, client: TestClient, db_session, payload: str
    ) -> None:
        """blog account_id は str 型。SQLAlchemy がパラメタライズして 404。"""
        headers = auth_header(client, "sqli-blog-account")
        resp = client.delete(f"/api/blog/accounts/{payload}", headers=headers)
        assert resp.status_code != 500, resp.text
        assert resp.status_code in (404, 422)
        # users テーブルが破壊されていないこと
        assert count_rows(db_session, User) >= 1

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_blog_articles_query_filter_handles_sqli(
        self, client: TestClient, payload: str
    ) -> None:
        """?platform= に SQLi を渡しても 200 + 空配列。"""
        headers = auth_header(client, "sqli-blog-articles")
        resp = client.get("/api/blog/articles", params={"platform": payload}, headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_notification_path_returns_404_for_sqli(
        self, client: TestClient, payload: str
    ) -> None:
        headers = auth_header(client, "sqli-notif")
        resp = client.patch(f"/api/notifications/{payload}/read", headers=headers)
        assert resp.status_code != 500, resp.text
        assert resp.status_code in (404, 422)

    @pytest.mark.parametrize("payload", SQLI_PAYLOADS)
    def test_master_data_name_treats_payload_as_literal(
        self, client: TestClient, payload: str
    ) -> None:
        """admin token 経由で SQLi を保存しても、文字列リテラル扱いで他テーブルが壊れない。"""
        resp = client.post(
            "/api/master-data/qualification",
            json={"name": payload, "sort_order": 0},
            headers={"Authorization": "Bearer test-admin-token"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == payload
        # 一覧 API が落ちずに 1 件返ること（DROP TABLE が解釈されていない証拠）
        listed = client.get("/api/master-data/qualification")
        assert listed.status_code == 200
        names = [item["name"] for item in listed.json()]
        assert payload in names
