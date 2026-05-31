"""master-data の admin 認可と /internal/tasks の Cloud Tasks ヘッダ要求の検証。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# テストで使う想定 audience（= CLOUD_TASKS_SERVICE_URL）。
_EXPECTED_AUDIENCE = "https://backend.example.com"


def _fake_oidc_verifier(claims: dict):
    """verify_oauth2_token の検証ダブルを生成する。

    実物と同じく audience 不一致で ValueError を送出する。これにより
    _verify_cloud_tasks_oidc() が audience=CLOUD_TASKS_SERVICE_URL を
    渡さなくなった場合にテストが失敗し、audience チェックを回帰で固定できる。
    """

    def _verify(token, request, audience):
        if audience != _EXPECTED_AUDIENCE:
            raise ValueError(f"audience 不一致: {audience!r}")
        return claims

    return _verify


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
    """Cloud Tasks コールバックにはキューヘッダーと OIDC を要求する。"""

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

    def test_missing_cloud_tasks_oidc_returns_403(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """TASK_RUNNER=cloud_tasks では OIDC Bearer token が無いと 403。"""
        monkeypatch.setenv("TASK_RUNNER", "cloud_tasks")
        monkeypatch.setenv("CLOUD_TASKS_SERVICE_URL", "https://backend.example.com")
        monkeypatch.setenv(
            "CLOUD_TASKS_SERVICE_ACCOUNT",
            "tasks@example.iam.gserviceaccount.com",
        )
        resp = client.post(
            "/internal/tasks/github_link",
            json={"user_id": "x"},
            headers={"X-CloudTasks-QueueName": "queue"},
        )
        assert resp.status_code == 403

    def test_invalid_cloud_tasks_oidc_claims_return_403(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OIDC の email が期待 SA と違う場合は 403。"""
        monkeypatch.setenv("TASK_RUNNER", "cloud_tasks")
        monkeypatch.setenv("CLOUD_TASKS_SERVICE_URL", "https://backend.example.com")
        monkeypatch.setenv(
            "CLOUD_TASKS_SERVICE_ACCOUNT",
            "tasks@example.iam.gserviceaccount.com",
        )
        monkeypatch.setattr(
            "app.routers.internal.id_token.verify_oauth2_token",
            _fake_oidc_verifier(
                {
                    "iss": "https://accounts.google.com",
                    "email": "attacker@example.iam.gserviceaccount.com",
                    "email_verified": True,
                }
            ),
        )
        resp = client.post(
            "/internal/tasks/github_link",
            json={"user_id": "x"},
            headers={
                "X-CloudTasks-QueueName": "queue",
                "Authorization": "Bearer token",
            },
        )
        assert resp.status_code == 403

    def test_valid_cloud_tasks_oidc_reaches_handler(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """正しいキューヘッダーと OIDC なら内部ハンドラまで到達する。"""
        monkeypatch.setenv("TASK_RUNNER", "cloud_tasks")
        monkeypatch.setenv("CLOUD_TASKS_SERVICE_URL", "https://backend.example.com")
        monkeypatch.setenv(
            "CLOUD_TASKS_SERVICE_ACCOUNT",
            "tasks@example.iam.gserviceaccount.com",
        )
        monkeypatch.setattr(
            "app.routers.internal.id_token.verify_oauth2_token",
            _fake_oidc_verifier(
                {
                    "iss": "https://accounts.google.com",
                    "email": "tasks@example.iam.gserviceaccount.com",
                    "email_verified": True,
                }
            ),
        )
        resp = client.post(
            "/internal/tasks/totally-unknown-type",
            json={},
            headers={
                "X-CloudTasks-QueueName": "queue",
                "Authorization": "Bearer token",
            },
        )
        assert resp.status_code == 400
