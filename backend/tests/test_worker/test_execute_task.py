"""execute_task のルーティングロジックと _safe_rollback の単体テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models import GitHubLinkCache
from app.repositories import UserRepository
from app.services.tasks.base import TaskType
from app.services.tasks.handlers import get_handler
from app.services.tasks.handlers.github_link import GitHubLinkHandler
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
        """GITHUB_LINK が登録ハンドラの run に正しくディスパッチされることを確認する。"""
        with (
            patch("app.services.tasks.worker.SessionLocal", return_value=db_session),
            patch.object(
                GitHubLinkHandler,
                "run",
                new_callable=AsyncMock,
            ) as mock_run,
            patch("app.services.tasks.worker._create_notification"),
        ):
            _run(
                execute_task(
                    TaskType.GITHUB_LINK,
                    {"user_id": "test-user", "github_username": "u"},
                )
            )

        mock_run.assert_called_once()

    def test_all_task_types_have_registered_handler(self):
        """TaskType に列挙された全種別がハンドラレジストリに登録済みであること。

        execute_task はレジストリ経由で汎用ディスパッチするため、種別を追加して
        ハンドラ登録を忘れると未登録として早期 return される。「黙って completed に
        なる」事故を防ぐため、全種別が登録済みであることをガードする。
        """
        missing = [t.name for t in TaskType if get_handler(t) is None]
        assert not missing, (
            f"ハンドラ未登録の TaskType があります: {missing}。"
            " services/tasks/handlers/__init__.py の _HANDLERS に登録してください。"
        )

    def test_execute_task_marks_dead_letter_on_error(self, db_session: Session):
        """予期しない例外が発生した場合（max_attempts=1）、例外が再 raise され、
        キャッシュが dead_letter へ遷移し error_message が永続化されること。

        内部関数 _mark_dead_letter の呼び出し引数ではなく結果 DB state を検証する
        （test_retry_flow.py と同じ契約を、実装詳細に結合しない形で守る）。"""
        user = UserRepository(db_session).create(
            "dead-letter-user", email="dl@test.com",
        )
        cache = GitHubLinkCache(user_id=user.id, status="processing")
        db_session.add(cache)
        db_session.commit()

        with (
            patch(
                "app.services.tasks.worker.SessionLocal",
                return_value=keep_open_session(db_session),
            ),
            patch.object(
                GitHubLinkHandler,
                "run",
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
        """タスク成功時に _create_notification が呼ばれること。"""
        mock_db = MagicMock()
        mock_session_local = MagicMock(return_value=mock_db)

        with (
            patch("app.services.tasks.worker.SessionLocal", mock_session_local),
            patch.object(
                GitHubLinkHandler,
                "run",
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
            "rollback-test-user", email="rollback@test.com"
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
