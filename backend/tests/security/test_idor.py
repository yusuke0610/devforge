"""IDOR (Insecure Direct Object References) 検証。
user A のリソースが user B からは見えない・操作できないことを固定化する。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.models import (
    BlogAccount,
    GitHubAnalysisCache,
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

    def test_blog_account_delete_does_not_touch_other_user_data(
        self, client: TestClient, db_session
    ) -> None:
        user_a = ensure_user(db_session, "idor-blog-del-a")
        account = BlogAccount(user_id=user_a.id, platform="zenn", username="user-a")
        db_session.add(account)
        db_session.commit()
        account_id = account.id
        headers_b = auth_header(client, "idor-blog-del-b")
        resp = client.delete(f"/api/blog/accounts/{account_id}", headers=headers_b)
        assert resp.status_code == 404
        remaining = db_session.scalar(select(BlogAccount).where(BlogAccount.id == account_id))
        assert remaining is not None

    def test_blog_account_patch_does_not_touch_other_user_data(
        self, client: TestClient, db_session
    ) -> None:
        user_a = ensure_user(db_session, "idor-blog-patch-a")
        account = BlogAccount(user_id=user_a.id, platform="qiita", username="user-a")
        db_session.add(account)
        db_session.commit()
        headers_b = auth_header(client, "idor-blog-patch-b")
        # 早期 404 のため verify_user_exists には到達しないが、念のためモック
        with patch(
            "app.routers.blog.accounts.verify_user_exists",
            new_callable=AsyncMock,
            return_value=True,
        ):
            resp = client.patch(
                "/api/blog/accounts/qiita",
                json={"username": "intruder"},
                headers=headers_b,
            )
        assert resp.status_code == 404
        unchanged = db_session.scalar(
            select(BlogAccount).where(
                BlogAccount.user_id == user_a.id, BlogAccount.platform == "qiita"
            )
        )
        assert unchanged.username == "user-a"

    def test_blog_account_sync_returns_404_for_other_user(
        self, client: TestClient, db_session
    ) -> None:
        user_a = ensure_user(db_session, "idor-blog-sync-a")
        account = BlogAccount(user_id=user_a.id, platform="zenn", username="user-a")
        db_session.add(account)
        db_session.commit()
        account_id = account.id
        headers_b = auth_header(client, "idor-blog-sync-b")
        resp = client.post(f"/api/blog/accounts/{account_id}/sync", headers=headers_b)
        assert resp.status_code == 404

    def test_intelligence_cache_does_not_leak_to_other_user(
        self, client: TestClient, db_session
    ) -> None:
        user_a = ensure_user(db_session, "idor-intel-cache-a")
        cache_a = GitHubAnalysisCache(
            user_id=user_a.id,
            analysis_result={"secret": "A だけが見るべきデータ"},
            status="completed",
        )
        db_session.add(cache_a)
        db_session.commit()
        headers_b = auth_header(client, "idor-intel-cache-b")
        resp = client.get("/api/intelligence/cache", headers=headers_b)
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("analysis_result") is None

    def test_notification_mark_read_does_not_touch_other_user(
        self, client: TestClient, db_session
    ) -> None:
        user_a = ensure_user(db_session, "idor-notif-a")
        notification = Notification(
            user_id=user_a.id,
            task_type="github_analysis",
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
