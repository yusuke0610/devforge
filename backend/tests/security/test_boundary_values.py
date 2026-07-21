"""境界値とパスパラメータ型違反の検証。空文字・上限超過・負数・型違反で 422/404 を返すか。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from conftest import auth_header

from ._helpers import RESUME_PAYLOAD


class TestBoundaryValues:
    """空文字・上限超過・負数などで 422 を返すことを固定化する。"""

    def test_resume_full_name_empty_returns_422(self, client: TestClient) -> None:
        headers = auth_header(client, "bound-resume-empty")
        resp = client.post(
            "/api/resumes",
            json={**RESUME_PAYLOAD, "full_name": ""},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_resume_full_name_over_max_length_returns_422(self, client: TestClient) -> None:
        headers = auth_header(client, "bound-resume-max")
        resp = client.post(
            "/api/resumes",
            json={**RESUME_PAYLOAD, "full_name": "あ" * 121},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_resume_career_summary_over_max_length_returns_422(
        self, client: TestClient
    ) -> None:
        headers = auth_header(client, "bound-resume-cs")
        resp = client.post(
            "/api/resumes",
            json={**RESUME_PAYLOAD, "career_summary": "x" * 2001},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_resume_team_member_count_negative_returns_422(self, client: TestClient) -> None:
        """team.members[].count は ge=0 制約。負数は 422。"""
        headers = auth_header(client, "bound-resume-team-neg")
        payload = {
            **RESUME_PAYLOAD,
            "experiences": [
                {
                    "company": "X",
                    "business_description": "Y",
                    "start_date": "2024-01",
                    "end_date": "2024-12",
                    "is_current": False,
                    "clients": [
                        {
                            "name": "",
                            "projects": [
                                {
                                    "name": "p",
                                    "team": {
                                        "total": "5",
                                        "members": [{"role": "SE", "count": -1}],
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        resp = client.post("/api/resumes", json=payload, headers=headers)
        assert resp.status_code == 422

    def test_master_data_name_empty_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/master-data/qualification",
            json={"name": "", "sort_order": 0},
            headers={"Authorization": "Bearer test-admin-token"},
        )
        assert resp.status_code == 422

    def test_master_data_name_over_max_length_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/master-data/qualification",
            json={"name": "x" * 201, "sort_order": 0},
            headers={"Authorization": "Bearer test-admin-token"},
        )
        assert resp.status_code == 422


class TestPathParamInjection:
    """UUID / int 期待箇所への型違反で 422、整数だが範囲外なら 404 を固定化する。"""

    def test_resume_invalid_uuid_returns_422(self, client: TestClient) -> None:
        headers = auth_header(client, "path-resume")
        resp = client.get("/api/resumes/not-a-uuid", headers=headers)
        assert resp.status_code == 422

    def test_resume_uuid_invalid_format_returns_422(self, client: TestClient) -> None:
        """UUID 形式に合わない文字列は 422 で弾かれ、DB に到達しない。"""
        headers = auth_header(client, "path-resume-bad")
        resp = client.get("/api/resumes/etc-passwd", headers=headers)
        assert resp.status_code == 422
