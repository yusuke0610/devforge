"""IDOR (Insecure Direct Object References) 検証。
user A のリソースが user B からは見えない・操作できないことを固定化する。
"""

from __future__ import annotations

from app.models import (
    GitHubLinkCache,
    Notification,
    Resume,
)
from app.repositories import UserRepository
from fastapi.testclient import TestClient
from sqlalchemy import select

from conftest import auth_header

from ._helpers import RESUME_PAYLOAD, create_resume, ensure_user


class TestIDOR:
    """user A のリソースは user B からは見えない・操作できないことを固定化する。"""

    def test_resume_get_by_id_returns_404_for_other_user(self, client: TestClient) -> None:
        headers_a = auth_header(client, "idor-resume-a")
        a_id = create_resume(client, headers_a)
        headers_b = auth_header(client, "idor-resume-b")
        resp = client.get(f"/api/resumes/{a_id}", headers=headers_b)
        assert resp.status_code == 404

    def test_resume_put_does_not_modify_other_user_data(
        self, client: TestClient, db_session
    ) -> None:
        headers_a = auth_header(client, "idor-resume-put-a")
        a_id = create_resume(client, headers_a)
        headers_b = auth_header(client, "idor-resume-put-b")
        resp = client.put(
            f"/api/resumes/{a_id}",
            json={**RESUME_PAYLOAD, "full_name": "侵入者"},
            headers=headers_b,
        )
        assert resp.status_code == 404
        # A の full_name が書き換わっていないこと
        user_a = UserRepository(db_session).get_by_username("idor-resume-put-a")
        assert user_a is not None
        a_resume = db_session.scalar(select(Resume).where(Resume.user_id == user_a.id))
        assert a_resume is not None
        assert a_resume.full_name == RESUME_PAYLOAD["full_name"]

    def test_resume_download_endpoints_reject_other_user(self, client: TestClient) -> None:
        headers_a = auth_header(client, "idor-resume-dl-a")
        a_id = create_resume(client, headers_a)
        headers_b = auth_header(client, "idor-resume-dl-b")
        for suffix in ("pdf", "markdown"):
            resp = client.get(f"/api/resumes/{a_id}/{suffix}", headers=headers_b)
            assert resp.status_code == 404, f"{suffix} should reject other-user access"

    def test_resume_delete_does_not_touch_other_user_data(
        self, client: TestClient, db_session
    ) -> None:
        """B が DELETE しても A の resume は残り、B 自身は 404。"""
        headers_a = auth_header(client, "idor-resume-del-a")
        create_resume(client, headers_a)
        headers_b = auth_header(client, "idor-resume-del-b")
        resp = client.delete("/api/resumes", headers=headers_b)
        assert resp.status_code == 404
        user_a = UserRepository(db_session).get_by_username("idor-resume-del-a")
        assert user_a is not None
        remaining = db_session.scalar(select(Resume).where(Resume.user_id == user_a.id))
        assert remaining is not None

    def test_intelligence_cache_does_not_leak_to_other_user(
        self, client: TestClient, db_session
    ) -> None:
        user_a = ensure_user(db_session, "idor-intel-cache-a")
        cache_a = GitHubLinkCache(
            user_id=user_a.id,
            result={"secret": "A だけが見るべきデータ"},
            status="completed",
        )
        db_session.add(cache_a)
        db_session.commit()
        headers_b = auth_header(client, "idor-intel-cache-b")
        resp = client.get("/api/github-link/cache", headers=headers_b)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("result") is None

    def test_notification_mark_read_does_not_touch_other_user(
        self, client: TestClient, db_session
    ) -> None:
        user_a = ensure_user(db_session, "idor-notif-a")
        notification = Notification(
            user_id=user_a.id,
            task_type="github_link",
            status="completed",
            title="A 宛通知",
            is_read=False,
        )
        db_session.add(notification)
        db_session.commit()
        notif_id = notification.id
        headers_b = auth_header(client, "idor-notif-b")
        resp = client.patch(f"/api/notifications/{notif_id}/read", headers=headers_b)
        assert resp.status_code == 404
        unchanged = db_session.scalar(select(Notification).where(Notification.id == notif_id))
        assert unchanged.is_read is False
