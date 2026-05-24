"""execute_task のルーティングロジックと _safe_rollback の単体テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import BlogSummaryCache
from app.repositories import UserRepository
from app.services.tasks.base import TaskType
from app.services.tasks.worker import (
    _safe_rollback,
    execute_task,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ._helpers import run_sync as _run


class TestExecuteTask:
    def test_known_task_type_routes_to_correct_handler(self, db_session: Session):
        """GITHUB_ANALYSIS が _run_github_analysis に正しくディスパッチされ、
        他のハンドラ関数は呼ばれないことを確認する。"""
        with (
            patch("app.services.tasks.worker.SessionLocal", return_value=db_session),
            patch(
                "app.services.tasks.worker._run_github_analysis",
                new_callable=AsyncMock,
            ) as mock_gh,
            patch(
                "app.services.tasks.worker._run_blog_summarize",
                new_callable=AsyncMock,
            ) as mock_blog,
            patch(
                "app.services.tasks.worker._run_career_analysis",
                new_callable=AsyncMock,
            ) as mock_career,
            patch("app.services.tasks.worker._create_notification"),
        ):
            _run(
                execute_task(
                    TaskType.GITHUB_ANALYSIS,
                    {"user_id": "test-user", "github_username": "u"},
                )
            )

        mock_gh.assert_called_once()
        mock_blog.assert_not_called()
        mock_career.assert_not_called()

    def test_resume_import_routes_to_resume_import_handler(self, db_session: Session):
        """RESUME_IMPORT が _run_resume_import にディスパッチされること。

        以前は execute_task の if/elif に RESUME_IMPORT 分岐が抜けていたため、
        ハンドラが呼ばれないまま completed ログ／通知が発行されていた
        （= フロントが永遠にポーリングを続ける不具合）。
        """
        with (
            patch("app.services.tasks.worker.SessionLocal", return_value=db_session),
            patch(
                "app.services.tasks.worker._run_resume_import",
                new_callable=AsyncMock,
            ) as mock_ri,
            patch(
                "app.services.tasks.worker._run_github_analysis",
                new_callable=AsyncMock,
            ) as mock_gh,
            patch("app.services.tasks.worker._create_notification"),
        ):
            _run(
                execute_task(
                    TaskType.RESUME_IMPORT,
                    {"user_id": "test-user", "import_id": "imp-1"},
                )
            )

        mock_ri.assert_called_once()
        mock_gh.assert_not_called()

    def test_all_task_types_have_dispatch_branch(self):
        """TaskType に列挙された全種別に execute_task のディスパッチ分岐があること。

        新しい TaskType を追加した際に worker.execute_task への分岐追加を
        忘れて「黙って completed になる」事故を防ぐためのガード。
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
        """予期しない例外が発生した場合（max_attempts=1）、_mark_dead_letter が
        呼ばれ例外が再 raise されること。"""
        mock_db = MagicMock()
        mock_session_local = MagicMock(return_value=mock_db)

        with (
            patch("app.services.tasks.worker.SessionLocal", mock_session_local),
            patch(
                "app.services.tasks.worker._run_github_analysis",
                new_callable=AsyncMock,
                side_effect=RuntimeError("予期しないクラッシュ"),
            ),
            patch("app.services.tasks.worker._mark_dead_letter") as mock_mark_dead_letter,
            patch("app.services.tasks.worker._create_notification"),
        ):
            with pytest.raises(RuntimeError, match="予期しないクラッシュ"):
                _run(
                    execute_task(
                        TaskType.GITHUB_ANALYSIS,
                        {"user_id": "test-user-id", "github_username": "u"},
                    )
                )

        mock_mark_dead_letter.assert_called_once()
        call_args = mock_mark_dead_letter.call_args
        assert call_args.args == (
            mock_db,
            TaskType.GITHUB_ANALYSIS,
            {"user_id": "test-user-id", "github_username": "u"},
        )
        assert isinstance(call_args.kwargs.get("error"), RuntimeError)

    def test_execute_task_creates_notification_on_success(self, db_session: Session):
        """タスク成功時に _create_notification が呼ばれること。"""
        mock_db = MagicMock()
        mock_session_local = MagicMock(return_value=mock_db)

        with (
            patch("app.services.tasks.worker.SessionLocal", mock_session_local),
            patch(
                "app.services.tasks.worker._run_blog_summarize",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("app.services.tasks.worker._create_notification") as mock_notify,
        ):
            _run(
                execute_task(
                    TaskType.BLOG_SUMMARIZE,
                    {"user_id": "notif-test-user"},
                )
            )

        mock_notify.assert_called_once_with(
            mock_db, TaskType.BLOG_SUMMARIZE, "notif-test-user", "completed"
        )


class TestSafeRollback:
    def test_rollback_after_failed_commit_restores_session(self, db_session: Session):
        """DB commit 失敗で実際にエラー状態に陥ったあと、_safe_rollback で
        セッションが再利用可能になること。

        `BlogSummaryCache.user_id` の unique 制約に違反させて IntegrityError を起こし、
        その後 `_safe_rollback` を呼ぶことで、ロールバックが効いて以降の commit が成功する
        という回復経路を実際に踏ませる。元実装は手動 `rollback()` のみで失敗状態を作らず、
        テストとして空回りしていた。
        """
        user = UserRepository(db_session).create(
            "rollback-test-user", hashed_password=None, email="rollback@test.com"
        )
        first_cache = BlogSummaryCache(user_id=user.id, status="processing")
        db_session.add(first_cache)
        db_session.commit()

        # 同じ user_id で 2 件目を追加 → unique 制約違反で commit が失敗し、
        # セッションは「次の操作で PendingRollbackError を投げる」状態になる
        duplicate = BlogSummaryCache(user_id=user.id, status="processing")
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
