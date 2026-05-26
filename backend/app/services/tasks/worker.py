"""バックグラウンドタスクのワーカー。

ローカル: BackgroundTasks から直接呼ばれる（retry_count=0, max_attempts=1 でリトライなし）。
Cloud: /internal/tasks/{type} エンドポイント経由で呼ばれる（Cloud Tasks ネイティブリトライ）。
どちらも同じ ``execute_task`` を経由してハンドラレジストリにディスパッチする。

タスク種別ごとの実体は ``services/tasks/handlers/`` 配下に分離されている。worker は
リトライ・dead_letter・通知などのタスク横断ロジックのみを担う。

セッション管理ポリシー (libSQL Hrana 失効対策):
  - ハンドラには ``SessionLocal`` (ファクトリ) をそのまま渡し、ハンドラ内で長時間
    処理の前後にセッションを開閉する。
  - worker の状態遷移更新（``_mark_dead_letter`` / ``_mark_retrying``）と通知
    （``_create_notification``）は、ハンドラとは独立した新規セッションで実行する。
    こうすることでハンドラ側のセッションが何らかの理由で失効していても、
    終端ステータスを確実に DB へ永続化できる。
"""

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...core.logging_utils import get_logger
from ...core.messages import get_notification
from ...db.database import SessionLocal
from ...repositories.notification import NotificationRepository
from .base import TaskType
from .exceptions import NonRetryableError
from .handlers import get_handler
from .handlers.base import SessionFactory

logger = get_logger(__name__)


# duration_ms がこの閾値を超えたら WARNING を出す（5分）
_SLOW_TASK_THRESHOLD_MS = 300_000


def _monotonic_ms_since(start: float) -> int:
    """``time.monotonic()`` の開始時点からの経過ミリ秒を返す。"""
    return int((time.monotonic() - start) * 1000)


async def execute_task(
    task_type: TaskType,
    payload: dict,
    *,
    retry_count: int = 0,
    max_attempts: int = 1,
) -> None:
    """タスクを実行する。各セクションごとに自前で DB セッションを作成・管理する。

    retry_count: Cloud Tasks の ``X-CloudTasks-TaskRetryCount`` ヘッダー値（0 始まり）。
    max_attempts: Cloud Tasks キューの ``retry_config.max_attempts``（総試行回数）。

    ローカル（BackgroundTasks）呼び出しではデフォルトの ``retry_count=0, max_attempts=1`` を使い、
    失敗時は即座に ``dead_letter`` へ遷移する（ローカルはネイティブリトライが無いため）。
    """

    user_id = payload.get("user_id", "unknown")
    record_id = payload.get("record_id")
    start = time.monotonic()

    logger.info(
        "タスク開始",
        extra={
            "task_id": task_type.value,
            "user_id": user_id,
            "record_id": record_id,
            "status": "running",
            "retry_count": retry_count,
            "max_attempts": max_attempts,
        },
    )

    if get_handler(task_type) is None:
        logger.error("不明なタスク種別: %s", task_type)
        return

    try:
        # 各 ``_run_*`` シムはテストからの patch ポイントとして残している。
        # 実体は ``services/tasks/handlers/`` 配下のハンドラ。
        # ハンドラには SessionLocal (ファクトリ) を渡し、ハンドラ内で長時間処理の
        # 前後にセッションを開閉させる。
        if task_type == TaskType.GITHUB_LINK:
            await _run_github_link(SessionLocal, payload)

        duration_ms = _monotonic_ms_since(start)
        logger.info(
            "タスク完了",
            extra={
                "task_id": task_type.value,
                "user_id": user_id,
                "record_id": record_id,
                "status": "completed",
                "duration_ms": duration_ms,
                "retry_count": retry_count,
            },
        )
        if duration_ms > _SLOW_TASK_THRESHOLD_MS:
            logger.warning(
                "タスクが低速です (%d ms)",
                duration_ms,
                extra={"task_id": task_type.value, "user_id": user_id, "duration_ms": duration_ms},
            )
        if isinstance(user_id, str) and user_id != "unknown":
            db = SessionLocal()
            try:
                _create_notification(db, task_type, user_id, "completed")
            finally:
                _safe_close(db)
    except NonRetryableError as exc:
        duration_ms = _monotonic_ms_since(start)
        logger.warning(
            "タスク失敗（リトライ不可）",
            extra={
                "task_id": task_type.value,
                "user_id": user_id,
                "record_id": record_id,
                "status": "dead_letter",
                "error_type": type(exc).__name__,
                "duration_ms": duration_ms,
                "retry_count": retry_count,
            },
            exc_info=True,
        )
        db = SessionLocal()
        try:
            _mark_dead_letter(db, task_type, payload, error=exc)
            if isinstance(user_id, str) and user_id != "unknown":
                _create_notification(db, task_type, user_id, "failed")
        finally:
            _safe_close(db)
        raise
    except Exception as exc:
        duration_ms = _monotonic_ms_since(start)
        is_final = retry_count >= max_attempts - 1
        if is_final:
            logger.error(
                "タスクが最終試行で失敗しました (dead_letter)",
                extra={
                    "task_id": task_type.value,
                    "user_id": user_id,
                    "record_id": record_id,
                    "status": "dead_letter",
                    "error_type": type(exc).__name__,
                    "duration_ms": duration_ms,
                    "retry_count": retry_count,
                    "max_attempts": max_attempts,
                },
                exc_info=True,
            )
            db = SessionLocal()
            try:
                _mark_dead_letter(db, task_type, payload, error=exc)
                if isinstance(user_id, str) and user_id != "unknown":
                    _create_notification(db, task_type, user_id, "failed")
            finally:
                _safe_close(db)
        else:
            logger.warning(
                "タスク失敗（リトライ予定）",
                extra={
                    "task_id": task_type.value,
                    "user_id": user_id,
                    "record_id": record_id,
                    "status": "retrying",
                    "error_type": type(exc).__name__,
                    "duration_ms": duration_ms,
                    "retry_count": retry_count,
                    "max_attempts": max_attempts,
                },
                exc_info=True,
            )
            db = SessionLocal()
            try:
                _mark_retrying(db, task_type, payload, retry_count, max_attempts, error=exc)
            finally:
                _safe_close(db)
        raise


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_close(db: Session) -> None:
    """セッションを best-effort で close する。失敗してもログだけ残して例外は外に出さない。"""
    try:
        db.close()
    except Exception:
        logger.warning("セッションのクローズに失敗しました", exc_info=True)


# ---------- ハンドラ薄ラッパー（後方互換）----------
# テストや既存呼び出しから ``_run_github_link`` を直接呼べるよう、
# ハンドラ実装への薄いシムを残す。引数は ``session_factory``。


async def _run_github_link(session_factory: SessionFactory, payload: dict) -> None:
    """GitHub 連携ハンドラへのシム。"""
    handler = get_handler(TaskType.GITHUB_LINK)
    if handler is None:
        raise ValueError(f"ハンドラが登録されていません: {TaskType.GITHUB_LINK}")
    await handler.run(session_factory, payload)


# ---------- 共通 ----------


def _safe_rollback(db: Session) -> None:
    """セッションをロールバックする（例外を握りつぶす）。

    新セッション運用に移行した後も、テスト・既存呼び出し向けに残している。
    DB commit 失敗後のセッション復旧が必要なケースで使用する。
    """
    try:
        db.rollback()
    except Exception:
        logger.warning("セッションのロールバックに失敗しました", exc_info=True)


def _create_notification(db: Session, task_type: TaskType, user_id: str, status: str) -> None:
    """タスク完了・失敗時に通知を作成する。失敗しても例外を握りつぶす（通知は補助機能）。"""
    try:
        title = get_notification(task_type.value, status)
        NotificationRepository.create(
            db=db, user_id=user_id, task_type=task_type.value, status=status, title=title
        )
    except Exception:
        logger.warning("通知の作成に失敗しました（タスク処理には影響しません）", exc_info=True)


def _get_task_record(db: Session, task_type: TaskType, payload: dict):
    """タスク種別に応じた DB レコードを取得する（ハンドラに委譲）。"""
    handler = get_handler(task_type)
    if handler is None:
        return None
    return handler.get_record(db, payload)


def _mark_dead_letter(
    db: Session,
    task_type: TaskType,
    payload: dict,
    *,
    error: Exception | None = None,
) -> None:
    """タスクを終端ステータス（``dead_letter``）に更新する。

    リトライ不可（NonRetryableError）またはリトライ上限に達したエラーで呼ばれる。
    失敗ステータスは ``dead_letter`` に一本化している。
    """
    try:
        error_message = str(error) if error else "予期しないエラーが発生しました"
        record = _get_task_record(db, task_type, payload)
        if record and record.status != "completed":
            record.status = "dead_letter"
            record.error_message = error_message
            record.completed_at = _now()
            db.commit()
    except Exception:
        logger.exception("タスク失敗マーク中にエラーが発生しました")


def _mark_retrying(
    db: Session,
    task_type: TaskType,
    payload: dict,
    retry_count: int,
    max_attempts: int,
    *,
    error: Exception | None = None,
) -> None:
    """タスクをリトライ待ち状態（``retrying``）に更新する。"""
    try:
        record = _get_task_record(db, task_type, payload)
        if record and record.status != "completed":
            record.status = "retrying"
            record.retry_count = retry_count
            record.max_retries = max_attempts
            if error is not None:
                record.error_message = str(error)
            db.commit()
    except Exception:
        logger.exception("タスクリトライマーク中にエラーが発生しました")
