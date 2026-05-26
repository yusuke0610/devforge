import logging
from datetime import datetime, timezone

from ..core.logging_utils import log_event
from ..core.security.auth import validate_jwt_key_pair
from .migrations import run_migrations


def bootstrap() -> None:
    validate_jwt_key_pair()
    # Turso (libSQL) がデータ永続化を担うため、起動時の DB 復元処理は不要
    run_migrations()
    log_event(logging.INFO, "bootstrap_migration_succeeded")

    from .database import SessionLocal
    from .seed import seed_master_data

    db = SessionLocal()
    try:
        seed_master_data(db)
        log_event(logging.INFO, "bootstrap_seed_succeeded")
        _reset_orphaned_tasks(db)
    finally:
        db.close()


def _reset_orphaned_tasks(db) -> None:
    """サーバ再起動で宙吊りになった pending/processing タスクを dead_letter にリセットする。

    BackgroundTasks はプロセス内コルーチンのため、サーバが強制終了されると
    _mark_dead_letter() が呼ばれずに DB ステータスが pending/processing のまま残る。
    放置すると次回起動時にフロントエンドが無限ポーリングに陥るため、起動時に掃除する。
    """
    from ..models.cache import GitHubLinkCache

    logger = logging.getLogger(__name__)
    now = datetime.now(timezone.utc)
    stale_statuses = ("pending", "processing")
    error_message = "サーバ再起動により処理が中断されました"

    # GitHubLinkCache
    gh_rows = (
        db.query(GitHubLinkCache)
        .filter(GitHubLinkCache.status.in_(stale_statuses))
        .all()
    )
    for row in gh_rows:
        row.status = "dead_letter"
        row.error_message = error_message
        row.completed_at = now
    if gh_rows:
        logger.warning(
            "孤立した GitHub 連携タスクをリセットしました",
            extra={"count": len(gh_rows)},
        )

    db.commit()


if __name__ == "__main__":
    bootstrap()
