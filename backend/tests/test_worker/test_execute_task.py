"""execute_task のルーティングロジックと _safe_rollback の単体テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import GitHubLinkCache
from app.repositories import UserRepository
from app.services.tasks.base import TaskType
from app.services.tasks.worker import (
    _safe_rollback,
    execute_task,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ._helpers import keep_open_session
from ._helpers import run_sync as _run


class TestExecuteTask:
    def test_known_task_type_routes_to_correct_handler(self, db_session: Session):
        """GITHUB_LINK が _run_github_link に正しくディスパッチされることを確認する。"""
        with (
            patch("app.services.tasks.worker.SessionLocal", return_value=db_session),
            patch(
                "app.services.tasks.worker._run_github_link",
                new_callable=AsyncMock,
            ) as mock_gh,
            patch("app.services.tasks.worker._create_notification"),
        ):
            _run(
                execute_task(
                    TaskType.GITHUB_LINK,
                    {"user_id": "test-user", "github_username": "u"},
                )
            )

        mock_gh.assert_called_once()

    def test_all_task_types_have_dispatch_branch(self):
        """
        Ensure every TaskType has a corresponding dispatch branch in worker.execute_task.
        
        Acts as a guard so adding a new TaskType without updating execute_task does not silently treat the task as completed; the test fails listing missing TaskType members.
        """
        import inspect

        from app.services.tasks import worker

        source = inspect.getsource(worker.execute_task)
        missing = [t.name for t in TaskType if f"TaskType.{t.name}" not in source]
        assert not missing, (
            f"execute_task に未対応の TaskType があります: {missing}。"
            " 対応するハンドラシムを追加し if/elif に分岐を足してください。"
        )

    def test_execute_task_marks_dead_letter_on_error(self, db_session: Session):
        """
        Verify that when a task handler raises an unexpected exception (max_attempts=1), the exception is re-raised and the corresponding GitHubLinkCache row transitions to the "dead_letter" state with the error message persisted and completed_at set.
        
        Asserts the post-failure database state (cache.status == "dead_letter", cache.error_message contains the exception text, and cache.completed_at is not None) rather than relying on internal helper call observations.
        """
        user = UserRepository(db_session).create(
            "github:dead-letter-user", hashed_password=None, email="dl@test.com",
        )
        cache = GitHubLinkCache(user_id=user.id, status="processing")
        db_session.add(cache)
        db_session.commit()

        with (
            patch(
                "app.services.tasks.worker.SessionLocal",
                return_value=keep_open_session(db_session),
            ),
            patch(
                "app.services.tasks.worker._run_github_link",
                new_callable=AsyncMock,
                side_effect=RuntimeError("予期しないクラッシュ"),
            ),
            patch("app.services.tasks.worker._create_notification"),
        ):
            with pytest.raises(RuntimeError, match="予期しないクラッシュ"):
                _run(
                    execute_task(
                        TaskType.GITHUB_LINK,
                        {"user_id": user.id, "github_username": "u"},
                    )
                )

        db_session.refresh(cache)
        assert cache.status == "dead_letter"
        assert "予期しないクラッシュ" in (cache.error_message or "")
        assert cache.completed_at is not None

    def test_execute_task_creates_notification_on_success(self, db_session: Session):
        """
        Verifies that a notification is created when a GitHub link task completes successfully.
        
        Ensures `_create_notification` is invoked once with the database session provided by `SessionLocal`, the `TaskType.GITHUB_LINK`, the task's `user_id`, and the `"completed"` status.
        """
        mock_db = MagicMock()
        mock_session_local = MagicMock(return_value=mock_db)

        with (
            patch("app.services.tasks.worker.SessionLocal", mock_session_local),
            patch(
                "app.services.tasks.worker._run_github_link",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.tasks.worker._create_notification") as mock_notify,
        ):
            _run(
                execute_task(
                    TaskType.GITHUB_LINK,
                    {"user_id": "notif-test-user", "github_username": "u"},
                )
            )

        mock_notify.assert_called_once_with(
            mock_db, TaskType.GITHUB_LINK, "notif-test-user", "completed"
        )


class TestSafeRollback:
    def test_rollback_after_failed_commit_restores_session(self, db_session: Session):
        """DB commit 失敗で実際にエラー状態に陥ったあと、_safe_rollback で
        セッションが再利用可能になること。

        `GitHubLinkCache.user_id` の unique 制約に違反させて IntegrityError を起こし、
        その後 `_safe_rollback` を呼ぶことで、ロールバックが効いて以降の commit が成功する
        という回復経路を実際に踏ませる。元実装は手動 `rollback()` のみで失敗状態を作らず、
        テストとして空回りしていた。
        """
        user = UserRepository(db_session).create(
            "rollback-test-user", hashed_password=None, email="rollback@test.com"
        )
        first_cache = GitHubLinkCache(user_id=user.id, status="processing")
        db_session.add(first_cache)
        db_session.commit()

        # 同じ user_id で 2 件目を追加 → unique 制約違反で commit が失敗し、
        # セッションは「次の操作で PendingRollbackError を投げる」状態になる
        duplicate = GitHubLinkCache(user_id=user.id, status="processing")
        db_session.add(duplicate)
        with pytest.raises(IntegrityError):
            db_session.commit()

        # _safe_rollback は例外を外に漏らさないこと（dirty な状態でも安全に呼べる）
        _safe_rollback(db_session)

        # ロールバック後にセッションが再利用可能であること。
        # 元の cache に対する更新 commit が通れば回復経路 OK と判断する。
        first_cache.status = "dead_letter"
        db_session.commit()
        db_session.refresh(first_cache)
        assert first_cache.status == "dead_letter"

    def test_safe_rollback_suppresses_exception(self):
        """rollback() が例外を送出しても _safe_rollback は例外を外に漏らさないこと。"""
        mock_db = MagicMock()
        mock_db.rollback.side_effect = Exception("DB 接続断")

        # 例外が外に漏れないこと
        _safe_rollback(mock_db)
        mock_db.rollback.assert_called_once()
