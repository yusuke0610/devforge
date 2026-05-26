"""認証なしでのアクセス検証。Cookie / CSRF なしで保護対象を叩いて 401/403 を返すかを固定化する。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from ._helpers import DUMMY_UUID

_PROTECTED_ENDPOINTS: list[tuple[str, str]] = [
    ("post", "/api/resumes"),
    ("get", "/api/resumes/latest"),
    ("get", f"/api/resumes/{DUMMY_UUID}"),
    ("put", f"/api/resumes/{DUMMY_UUID}"),
    ("delete", "/api/resumes"),
    ("get", f"/api/resumes/{DUMMY_UUID}/pdf"),
    ("get", f"/api/resumes/{DUMMY_UUID}/markdown"),
    ("get", "/api/blog/accounts"),
    ("post", "/api/blog/accounts"),
    ("patch", "/api/blog/accounts/zenn"),
    ("delete", "/api/blog/accounts/x"),
    ("get", "/api/blog/articles"),
    ("post", "/api/blog/accounts/x/sync"),
    ("get", "/api/blog/score"),
    ("get", "/api/github-link/cache"),
    ("get", "/api/github-link/cache/status"),
    ("get", "/api/github-link/progress"),
    ("post", "/api/github-link/run"),
    ("post", "/api/github-link/run/retry"),
    ("get", "/api/notifications"),
    ("get", "/api/notifications/unread-count"),
    ("patch", "/api/notifications/abc/read"),
    ("post", "/api/notifications/read-all"),
]


class TestNoAuthAccess:
    """Cookie / CSRF なしで保護対象を叩くと 401/403 が返ることを固定化する。"""

    @pytest.mark.parametrize("method,path", _PROTECTED_ENDPOINTS)
    def test_protected_endpoint_rejects_unauthenticated(
        self, client: TestClient, method: str, path: str
    ) -> None:
        resp = getattr(client, method)(path)
        assert resp.status_code in (401, 403), (
            f"{method.upper()} {path} の status は 401/403 期待だが {resp.status_code}: {resp.text}"
        )

    def test_health_endpoint_is_public(self, client: TestClient) -> None:
        assert client.get("/health").status_code == 200

    def test_master_data_list_is_public(self, client: TestClient) -> None:
        """マスタの GET は公開（フロントが認証前に取得する設計）。"""
        assert client.get("/api/master-data/qualification").status_code == 200
        assert client.get("/api/master-data/technology-stack").status_code == 200
