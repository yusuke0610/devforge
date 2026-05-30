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
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import id_token

from ..core import env_keys
from ..core.messages import get_error
from ..services.tasks.base import TaskType
from ..services.tasks.exceptions import NonRetryableError, RetryableError
from ..services.tasks.worker import execute_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/tasks", tags=["internal"])


def _get_bearer_token(request: Request) -> str:
    """Authorization ヘッダーから Bearer token を取り出す。"""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return ""
    return token.strip()


def _verify_cloud_tasks_oidc(request: Request) -> bool:
    """Cloud Tasks OIDC トークンの audience と発行元サービスアカウントを検証する。"""
    expected_audience = os.environ.get(env_keys.CLOUD_TASKS_SERVICE_URL, "").strip()
    expected_service_account = os.environ.get(env_keys.CLOUD_TASKS_SERVICE_ACCOUNT, "").strip()
    token = _get_bearer_token(request)
    if not expected_audience or not expected_service_account or not token:
        return False

    try:
        claims = id_token.verify_oauth2_token(
            token,
            GoogleAuthRequest(),
            audience=expected_audience,
        )
    except ValueError:
        logger.warning("Cloud Tasks OIDC トークン検証に失敗しました", exc_info=True)
        return False

    issuer = claims.get("iss")
    email = claims.get("email")
    email_verified = claims.get("email_verified")
    allowed_issuers = {"https://accounts.google.com", "accounts.google.com"}
    return (
        issuer in allowed_issuers
        and email == expected_service_account
        and email_verified is True
    )


def _verify_request(request: Request) -> bool:
    """Cloud Tasks からのリクエストか検証する。

    TASK_RUNNER=cloud_tasks の場合は X-CloudTasks-QueueName と OIDC を必須とする。
    未設定（空文字含む）はローカル／テスト環境とみなし無条件で許可する。
    """
    if os.environ.get(env_keys.TASK_RUNNER, "").strip() != "cloud_tasks":
        return True
    queue_name = request.headers.get("X-CloudTasks-QueueName")
    return bool(queue_name) and _verify_cloud_tasks_oidc(request)


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
        raise HTTPException(
            status_code=400,
            detail=get_error("task.unknown_task_type", task_type=task_type),
        )

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
    except Exception:
        # 予期しないエラーは 500 を返し Cloud Tasks のリトライに任せる
        logger.exception(
            "タスク実行で予期しないエラー",
            extra={"task_id": task_type, "retry_count": retry_count},
        )
        # 例外詳細は上の logger.exception でのみ残し、クライアント応答へは補間しない（info leak 防止）
        raise HTTPException(
            status_code=500,
            detail=get_error("task.execution_failed"),
        )

    return {"status": "ok"}
