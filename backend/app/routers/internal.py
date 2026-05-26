"""
内部タスクエンドポイント（Cloud Tasks コールバック用）。

POST /internal/tasks/{task_type} — Cloud Tasks からのタスク実行リクエストを受け付ける

HTTP ステータスコードで Cloud Tasks のリトライ挙動を制御する:
- 2xx / 4xx: Cloud Tasks はリトライしない
- 5xx / 429: Cloud Tasks がキューの ``retry_config`` に従い exponential backoff でリトライ
"""

import logging
import os

from fastapi import APIRouter, HTTPException, Request

from ..core import env_keys
from ..core.messages import get_error
from ..services.tasks.base import TaskType
from ..services.tasks.exceptions import NonRetryableError, RetryableError
from ..services.tasks.worker import execute_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/tasks", tags=["internal"])


def _verify_request(request: Request) -> bool:
    """Cloud Tasks からのリクエストか検証する。

    TASK_RUNNER=cloud_tasks の場合のみ X-CloudTasks-QueueName ヘッダーを必須とする。
    未設定（空文字含む）はローカル／テスト環境とみなし無条件で許可する。
    """
    if os.environ.get(env_keys.TASK_RUNNER, "").strip() != "cloud_tasks":
        return True
    queue_name = request.headers.get("X-CloudTasks-QueueName")
    return bool(queue_name)


def _get_max_attempts() -> int:
    """Cloud Tasks キューの ``retry_config.max_attempts`` を環境変数から取得する。

    インフラ（``infra/modules/cloud_tasks``）の値と一致させる必要がある。
    """
    try:
        return max(1, int(os.environ.get(env_keys.TASK_MAX_ATTEMPTS, "3")))
    except ValueError:
        return 3


@router.post("/{task_type}")
async def handle_task(task_type: str, request: Request):
    """Cloud Tasks コールバックまたはローカルテスト用エンドポイント。"""
    if not _verify_request(request):
        raise HTTPException(
            status_code=403,
            detail=get_error("task.internal_unauthorized"),
        )

    try:
        task_type_enum = TaskType(task_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不明なタスク種別: {task_type}")

    payload = await request.json()

    try:
        retry_count = int(request.headers.get("X-CloudTasks-TaskRetryCount", "0"))
    except ValueError:
        retry_count = 0
    max_attempts = _get_max_attempts()

    try:
        await execute_task(
            task_type_enum,
            payload,
            retry_count=retry_count,
            max_attempts=max_attempts,
        )
    except NonRetryableError as exc:
        # 2xx で応答し Cloud Tasks のリトライを止める（状態は worker 側で failed に更新済み）
        logger.warning(
            "タスクをリトライ不可として確定しました",
            extra={"task_id": task_type, "retry_count": retry_count},
        )
        return {"status": "non_retryable", "error": str(exc)}
    except RetryableError as exc:
        # Retry-After が指定されていれば 429 + ヘッダーで返し、なければ 503 で返す
        headers: dict[str, str] = {}
        status_code = 503
        if exc.retry_after is not None:
            headers["Retry-After"] = str(int(exc.retry_after))
            status_code = 429
        raise HTTPException(status_code=status_code, detail=str(exc), headers=headers)
    except Exception as exc:
        # 予期しないエラーは 500 を返し Cloud Tasks のリトライに任せる
        logger.exception(
            "タスク実行で予期しないエラー",
            extra={"task_id": task_type, "retry_count": retry_count},
        )
        raise HTTPException(
            status_code=500,
            detail=f"タスク実行中に予期しないエラーが発生しました: {exc}",
        )

    return {"status": "ok"}
