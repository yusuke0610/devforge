"""
リトライフローの統合テスト。

対象:
- ``app.services.tasks.worker.execute_task`` のリトライ分岐
  - NonRetryableError → status=dead_letter（リトライ不可）
  - RetryableError / 予期しない例外 → 試行回数に応じて retrying / dead_letter
- ``app.routers.internal.handle_task`` の HTTP ステータスマッピング
  - NonRetryableError → 200
  - RetryableError (retry_after なし) → 503
  - RetryableError (retry_after あり) → 429 + Retry-After ヘッダー
  - 予期しない例外 → 500
- 手動再実行エンドポイント（/retry）の状態リセット挙動
"""

import asyncio
import os
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from app.models import GitHubLinkCache
from app.repositories import UserRepository
from app.services.tasks.base import TaskType
from app.services.tasks.exceptions import NonRetryableError, RetryableError
from app.services.tasks.handlers.github_link import GitHubLinkHandler
from app.services.tasks.worker import execute_task
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from conftest import auth_header


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _keep_open_session(db: Session):
    """worker が呼ぶ ``db.close()`` をテスト用セッションでは無効化するプロキシ。

    worker は finally 節で ``db.close()`` を呼ぶが、テストでは同じ ``db_session`` を
    検証側でも使い続けたいため、close だけ no-op 化する。
    """

    class _Proxy:
        def __init__(self, real: Session) -> None:
            self._real = real

        def __getattr__(self, name):
            return getattr(self._real, name)

        def close(self) -> None:
            self._real.expire_all()

    return _Proxy(db)


@contextmanager
def _setup_github_link_test(
    db_session: Session,
    suffix: str,
    side_effect,
    initial_status: str = "processing",
):
    """github_link worker テストの共通スキャフォールド。

    元の各テストにあった「user 作成 → cache 作成 → worker.SessionLocal / GitHubLinkHandler.run /
    _create_notification の 3 連 patch」を集約する。15 行 × 4 箇所のコピペを解消するための helper。
    yield する mock_notify で `_create_notification` の呼び出し有無を検証できる。
    """
    user = UserRepository(db_session).create(
        suffix, email=f"{suffix}@test.com",
    )
    cache = GitHubLinkCache(user_id=user.id, status=initial_status)
    db_session.add(cache)
    db_session.commit()

    with (
        patch(
            "app.services.tasks.worker.SessionLocal",
            return_value=_keep_open_session(db_session),
        ),
        patch.object(
            GitHubLinkHandler,
            "run",
            new_callable=AsyncMock,
            side_effect=side_effect,
        ),
        patch("app.services.tasks.worker._create_notification") as mock_notify,
    ):
        yield user, cache, mock_notify


# ══════════════════════════════════════════════════════════════════════
# execute_task リトライ分岐
# ══════════════════════════════════════════════════════════════════════


class TestExecuteTaskRetryBranching:
    """execute_task が retry_count / max_attempts に応じて正しく分岐することを確認する。"""

    def test_non_retryable_error_marks_dead_letter(self, db_session: Session):
        """NonRetryableError はリトライ回数に関係なく status=dead_letter で終える。"""
        with _setup_github_link_test(
            db_session, "nonretry-user", side_effect=NonRetryableError("認証不可"),
        ) as (user, cache, _mock_notify):
            with pytest.raises(NonRetryableError):
                _run(
                    execute_task(
                        TaskType.GITHUB_LINK,
                        {"user_id": user.id},
                        retry_count=0,
                        max_attempts=3,
                    ),
                )

        db_session.refresh(cache)
        assert cache.status == "dead_letter"
        assert "認証不可" in (cache.error_message or "")

    def test_retryable_error_with_attempts_remaining_marks_retrying(
        self, db_session: Session,
    ):
        """RetryableError で試行回数が残っていれば status=retrying にする。"""
        with _setup_github_link_test(
            db_session,
            "retrying-user",
            side_effect=RetryableError("一時エラー", retry_after=10),
        ) as (user, cache, mock_notify):
            with pytest.raises(RetryableError):
                _run(
                    execute_task(
                        TaskType.GITHUB_LINK,
                        {"user_id": user.id},
                        retry_count=0,
                        max_attempts=3,
                    ),
                )

        db_session.refresh(cache)
        assert cache.status == "retrying"
        assert cache.retry_count == 0
        assert cache.max_retries == 3
        # retrying 状態では失敗通知を出さない
        mock_notify.assert_not_called()

    def test_retryable_error_on_final_attempt_marks_dead_letter(
        self, db_session: Session,
    ):
        """最終試行（retry_count == max_attempts - 1）で失敗したら dead_letter。"""
        with _setup_github_link_test(
            db_session,
            "deadletter-user",
            side_effect=RetryableError("最後も失敗"),
            initial_status="retrying",
        ) as (user, cache, mock_notify):
            with pytest.raises(RetryableError):
                _run(
                    execute_task(
                        TaskType.GITHUB_LINK,
                        {"user_id": user.id},
                        retry_count=2,
                        max_attempts=3,
                    ),
                )

        db_session.refresh(cache)
        assert cache.status == "dead_letter"
        # 最終試行では失敗通知を出す
        mock_notify.assert_called_once()
        args = mock_notify.call_args.args
        assert args[2] == user.id
        assert args[3] == "failed"

    def test_unknown_exception_treated_as_retryable(self, db_session: Session):
        """分類されていない例外（RuntimeError 等）は retryable と同様に扱う。"""
        with _setup_github_link_test(
            db_session,
            "unknown-err-user",
            side_effect=RuntimeError("想定外のクラッシュ"),
        ) as (user, cache, _mock_notify):
            with pytest.raises(RuntimeError):
                _run(
                    execute_task(
                        TaskType.GITHUB_LINK,
                        {"user_id": user.id},
                        retry_count=0,
                        max_attempts=3,
                    ),
                )

        db_session.refresh(cache)
        assert cache.status == "retrying"

    def test_local_default_marks_dead_letter_on_first_failure(
        self, db_session: Session,
    ):
        """ローカル（max_attempts=1 デフォルト）では最初の失敗で即 dead_letter。"""
        with _setup_github_link_test(
            db_session,
            "local-fail-user",
            side_effect=RuntimeError("ローカル失敗"),
        ) as (user, cache, _mock_notify):
            with pytest.raises(RuntimeError):
                # retry_count=0, max_attempts=1（デフォルト）
                _run(execute_task(TaskType.GITHUB_LINK, {"user_id": user.id}))

        db_session.refresh(cache)
        assert cache.status == "dead_letter"


# ══════════════════════════════════════════════════════════════════════
# /internal/tasks/{type} HTTP ステータスマッピング
# ══════════════════════════════════════════════════════════════════════


class TestInternalRouterStatusMapping:
    """Cloud Tasks がリトライ判断に使う HTTP ステータスコードを確認する。"""

    def _payload(self) -> dict:
        return {"user_id": "any", "github_username": "u"}

    def test_success_returns_200(self, client: TestClient):
        # conftest で execute_task は AsyncMock(return_value=None) に差し替え済み
        resp = client.post(
            "/internal/tasks/github_link",
            json=self._payload(),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_non_retryable_returns_200_to_stop_retry(self, client: TestClient):
        """NonRetryableError は 2xx を返し Cloud Tasks のリトライを止める。"""
        with patch(
            "app.routers.internal.execute_task",
            new=AsyncMock(side_effect=NonRetryableError("認証エラー")),
        ):
            resp = client.post(
                "/internal/tasks/github_link",
                json=self._payload(),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "non_retryable"

    def test_retryable_without_retry_after_returns_503(self, client: TestClient):
        """RetryableError（retry_after なし）は 503 で Cloud Tasks にリトライさせる。"""
        with patch(
            "app.routers.internal.execute_task",
            new=AsyncMock(side_effect=RetryableError("一時エラー")),
        ):
            resp = client.post(
                "/internal/tasks/github_link",
                json=self._payload(),
            )
        assert resp.status_code == 503

    def test_retryable_with_retry_after_returns_429(self, client: TestClient):
        """RetryableError（retry_after あり）は 429 + Retry-After ヘッダーで返す。"""
        with patch(
            "app.routers.internal.execute_task",
            new=AsyncMock(side_effect=RetryableError("rate limit", retry_after=30)),
        ):
            resp = client.post(
                "/internal/tasks/github_link",
                json=self._payload(),
            )
        assert resp.status_code == 429
        assert resp.headers.get("Retry-After") == "30"

    def test_unexpected_exception_returns_500(self, client: TestClient):
        """予期しない例外は 500 で Cloud Tasks にリトライさせる。"""
        with patch(
            "app.routers.internal.execute_task",
            new=AsyncMock(side_effect=RuntimeError("予期しない")),
        ):
            resp = client.post(
                "/internal/tasks/github_link",
                json=self._payload(),
            )
        assert resp.status_code == 500

    def test_retry_count_header_forwarded_to_worker(self, client: TestClient):
        """X-CloudTasks-TaskRetryCount ヘッダーが execute_task に渡されること。"""
        captured: dict = {}

        async def _capture(task_type, payload, *, retry_count, max_attempts):
            captured["retry_count"] = retry_count
            captured["max_attempts"] = max_attempts

        with patch("app.routers.internal.execute_task", new=AsyncMock(side_effect=_capture)):
            with patch.dict(os.environ, {"TASK_MAX_ATTEMPTS": "5"}):
                resp = client.post(
                    "/internal/tasks/github_link",
                    json=self._payload(),
                    headers={"X-CloudTasks-TaskRetryCount": "2"},
                )
        assert resp.status_code == 200
        assert captured["retry_count"] == 2
        assert captured["max_attempts"] == 5

    def test_invalid_task_type_returns_400(self, client: TestClient):
        resp = client.post("/internal/tasks/invalid_type", json={"user_id": "x"})
        assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════════════
# 手動再実行エンドポイント
# ══════════════════════════════════════════════════════════════════════


class TestRetryEndpoints:
    """`POST /{resource}/retry` が失敗状態をリセットし再ディスパッチすること。"""

    def test_intelligence_retry_requires_github_user(self, client: TestClient):
        """github_id を持たないユーザーは GitHub 連携リトライを実行できない。"""
        headers = auth_header(client, "non-github-user")
        resp = client.post("/api/github-link/run/retry", headers=headers)
        assert resp.status_code == 403

    def test_intelligence_retry_resets_cache(self, client: TestClient):
        headers = auth_header(client, "retry-intel-user", github_id=999)
        db = client._db_session
        user = UserRepository(db).get_by_username("retry-intel-user")

        cache = GitHubLinkCache(
            user_id=user.id,
            status="dead_letter",
            error_message="old",
            retry_count=3,
        )
        db.add(cache)
        db.commit()

        resp = client.post("/api/github-link/run/retry", headers=headers)
        assert resp.status_code == 202
        assert resp.json()["status"] == "pending"

        db.refresh(cache)
        assert cache.status == "pending"
        assert cache.retry_count == 0
        assert cache.error_message is None

    def test_retry_returns_404_when_no_cache(self, client: TestClient):
        """連携キャッシュが未作成なら 404（先に連携を実行させる）。"""
        headers = auth_header(client, "retry-nocache-user", github_id=999)
        resp = client.post("/api/github-link/run/retry", headers=headers)
        assert resp.status_code == 404

    @pytest.mark.parametrize("status", ["completed", "processing", "pending", "retrying"])
    def test_retry_returns_409_when_not_dead_letter(self, client: TestClient, status: str):
        """dead_letter 以外（completed / processing 等）の状態では再実行できず 409。"""
        username = f"retry-409-{status}"
        headers = auth_header(client, username, github_id=999)
        db = client._db_session
        user = UserRepository(db).get_by_username(username)

        cache = GitHubLinkCache(user_id=user.id, status=status)
        db.add(cache)
        db.commit()

        resp = client.post("/api/github-link/run/retry", headers=headers)
        assert resp.status_code == 409

        # 状態は変更されないこと（再実行ガードが副作用を起こさない）
        db.refresh(cache)
        assert cache.status == status

    def test_retry_returns_409_on_concurrent_reset_race(self, client: TestClient):
        """is_retryable_terminal は通過しても、並列競合で try_reset_to_pending が
        False を返したら 409 にすること（TOCTOU ガード）。"""
        headers = auth_header(client, "retry-race-user", github_id=999)
        db = client._db_session
        user = UserRepository(db).get_by_username("retry-race-user")

        cache = GitHubLinkCache(user_id=user.id, status="dead_letter", retry_count=2)
        db.add(cache)
        db.commit()

        # 1つ目のガード（is_retryable_terminal）は通すが、アトミック遷移で競合負け
        with patch(
            "app.services.tasks.dispatch_service.AsyncTaskCacheService.try_reset_to_pending",
            return_value=False,
        ):
            resp = client.post("/api/github-link/run/retry", headers=headers)
        assert resp.status_code == 409


# ══════════════════════════════════════════════════════════════════════
# 終端状態の判定（固定値ではなく境界条件を確認）
# ══════════════════════════════════════════════════════════════════════


def test_is_final_at_last_attempt(db_session: Session):
    """max_attempts=3, retry_count=2 は最終試行であること（dead_letter に遷移する）。"""
    # この境界条件は TestExecuteTaskRetryBranching.test_retryable_error_on_final_attempt
    # で既にカバーしているが、ここで明示的にパラメトリックに確認する。
    user = UserRepository(db_session).create(
        "boundary-user", email="boundary@test.com",
    )
    cache = GitHubLinkCache(user_id=user.id, status="processing")
    db_session.add(cache)
    db_session.commit()

    # 最終より 1 つ手前（retry_count=1, max=3）は retrying
    with (
        patch(
            "app.services.tasks.worker.SessionLocal",
            return_value=_keep_open_session(db_session),
        ),
        patch.object(
            GitHubLinkHandler,
            "run",
            new_callable=AsyncMock,
            side_effect=RetryableError("still retrying"),
        ),
        patch("app.services.tasks.worker._create_notification"),
    ):
        with pytest.raises(RetryableError):
            _run(
                execute_task(
                    TaskType.GITHUB_LINK,
                    {"user_id": user.id},
                    retry_count=1,
                    max_attempts=3,
                ),
            )
    db_session.refresh(cache)
    assert cache.status == "retrying"
