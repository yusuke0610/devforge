"""master-data の admin 認可と /internal/tasks の Cloud Tasks ヘッダ要求の検証。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestAdminTokenRequired:
    """master-data の書込系は admin Bearer token を要求する。"""

    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("post", "/api/master-data/qualification", {"name": "x", "sort_order": 0}),
            ("put", "/api/master-data/qualification/anything", {"name": "x", "sort_order": 0}),
            ("delete", "/api/master-data/qualification/anything", None),
            (
                "post",
                "/api/master-data/technology-stack",
                {"category": "c", "name": "x", "sort_order": 0},
            ),
            (
                "put",
                "/api/master-data/technology-stack/anything",
                {"category": "c", "name": "x", "sort_order": 0},
            ),
            ("delete", "/api/master-data/technology-stack/anything", None),
        ],
    )
    def test_missing_authorization_returns_401(
        self, client: TestClient, method: str, path: str, body: dict | None
    ) -> None:
        if body is None:
            resp = getattr(client, method)(path)
        else:
            resp = getattr(client, method)(path, json=body)
        assert resp.status_code == 401

    def test_wrong_bearer_token_returns_403(self, client: TestClient) -> None:
        resp = client.post(
            "/api/master-data/qualification",
            json={"name": "x", "sort_order": 0},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 403


class TestInternalSecret:
    """Cloud Tasks コールバックには X-CloudTasks-QueueName を要求する。"""

    def test_unknown_task_type_returns_400(self, client: TestClient) -> None:
        resp = client.post("/internal/tasks/totally-unknown-type", json={})
        assert resp.status_code == 400

    def test_missing_cloud_tasks_header_returns_403(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TASK_RUNNER=cloud_tasks では X-CloudTasks-QueueName が無いと 403。"""
        monkeypatch.setenv("TASK_RUNNER", "cloud_tasks")
        resp = client.post("/internal/tasks/github_link", json={"user_id": "x"})
        assert resp.status_code == 403
