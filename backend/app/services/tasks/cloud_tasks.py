"""Cloud Tasks 用ディスパッチャー。

リトライはキュー側の ``retry_config`` に任せる（ネイティブリトライ方式）。
ワーカーが HTTP 5xx を返すと Cloud Tasks が exponential backoff で自動再試行する。
"""

import json
import os

from google.cloud import tasks_v2

from ...core import env_keys
from .base import TaskDispatcher, TaskType


class CloudTasksDispatcher(TaskDispatcher):
    """Google Cloud Tasks を利用して HTTP コールバックでタスクを実行する。"""

    def __init__(self):
        self._client = tasks_v2.CloudTasksClient()
        self._queue = self._client.queue_path(
            os.environ[env_keys.GCP_PROJECT_ID],
            os.environ.get(env_keys.CLOUD_TASKS_LOCATION, "asia-northeast1"),
            os.environ.get(env_keys.CLOUD_TASKS_QUEUE, "devforge-ai-tasks"),
        )
        self._service_url = os.environ[env_keys.CLOUD_TASKS_SERVICE_URL]
        self._service_account = os.environ.get(env_keys.CLOUD_TASKS_SERVICE_ACCOUNT, "")
        self._internal_secret = os.environ.get(env_keys.INTERNAL_SECRET, "")

    async def dispatch(self, task_type: TaskType, payload: dict) -> None:
        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{self._service_url}/internal/tasks/{task_type.value}",
                headers={
                    "Content-Type": "application/json",
                    "X-Internal-Secret": self._internal_secret,
                },
                body=json.dumps(payload).encode(),
                oidc_token=tasks_v2.OidcToken(
                    service_account_email=self._service_account,
                    audience=self._service_url,
                ),
            ),
            dispatch_deadline={"seconds": 1800},
        )
        self._client.create_task(
            tasks_v2.CreateTaskRequest(parent=self._queue, task=task),
        )
