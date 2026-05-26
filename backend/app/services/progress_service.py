"""タスクの進捗情報を Redis に書き込む・読み出すユーティリティ。"""

import json
import logging

logger = logging.getLogger(__name__)

_KEY_PREFIX = "devforge:progress:"
_TTL_SECONDS = 3600
# Redis にデータがない場合のフォールバック値。
# 呼び出し側がタスク種別ごとに override する想定（GitHub 連携: 5、resume_import: 3 等）。
_DEFAULT_TOTAL_STEPS = 5


async def set_progress(
    task_id: str,
    step_index: int,
    total_steps: int,
    step_label: str,
    sub_progress: dict | None = None,
) -> None:
    """タスクの進捗を Redis に保存する。

    Redis が利用不可の場合はログを出して処理を継続する。
    タスク本体を止めないよう例外は握りつぶさず警告ログのみ出す。
    """
    from ..core.redis_client import get_redis_client

    try:
        client = get_redis_client()
        if client is None:
            return

        data = {
            "task_id": task_id,
            "step_index": step_index,
            "total_steps": total_steps,
            "step_label": step_label,
            "sub_progress": sub_progress,
        }
        key = f"{_KEY_PREFIX}{task_id}"
        await client.setex(key, _TTL_SECONDS, json.dumps(data, ensure_ascii=False))
    except Exception:
        logger.warning(
            "進捗情報の書き込みに失敗しました (task_id=%s)", task_id, exc_info=True
        )


async def get_progress(
    task_id: str,
    *,
    default_total_steps: int = _DEFAULT_TOTAL_STEPS,
) -> dict:
    """Redis から進捗情報を取得する。

    データがない場合（タスク未開始・Redis 障害）はデフォルト値を返す。
    default_total_steps はタスク種別ごとに想定全ステップ数を渡す
    （フロントの進捗バー初期表示用。実値は ``set_progress`` 後に上書きされる）。
    """
    from ..core.redis_client import get_redis_client

    default: dict = {
        "task_id": task_id,
        "step_index": 0,
        "total_steps": default_total_steps,
        "step_label": None,
        "sub_progress": None,
    }
    try:
        client = get_redis_client()
        if client is None:
            return default

        key = f"{_KEY_PREFIX}{task_id}"
        raw = await client.get(key)
        if raw is None:
            return default

        return json.loads(raw)
    except Exception:
        logger.warning(
            "進捗情報の取得に失敗しました (task_id=%s)", task_id, exc_info=True
        )
        return default
