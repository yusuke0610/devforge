"""Agent エンドポイントのユーザ単位日次レート制限（#521 / ADR-0023）。

プリペイド課金（残高チェック）に代わる abuse 防止。ユーザ×日ごとのリクエスト回数を
原子的に増やし、`AGENT_DAILY_LIMIT` を超えたら `AgentRateLimitExceededError` を raise する。
日次リセットは JST 基準。
"""

import os
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from ...core import env_keys
from ...core.date_utils import JST
from ...repositories.agent_rate_limit import AgentRateLimitRepository

# 未設定時の既定日次上限。Haiku は安価（$1/$5 per 1M tokens）なので緩めに設定する。
DEFAULT_AGENT_DAILY_LIMIT = 50


class AgentRateLimitExceededError(Exception):
    """日次リクエスト上限を超過した。"""

    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"Agent の 1 日あたりの利用上限（{limit} 回）に達しました")


def resolve_daily_limit() -> int:
    """`AGENT_DAILY_LIMIT` から日次上限を解決する。未設定・不正値は既定値を使う。"""
    raw = os.getenv(env_keys.AGENT_DAILY_LIMIT)
    if raw is None or not raw.strip():
        return DEFAULT_AGENT_DAILY_LIMIT
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_AGENT_DAILY_LIMIT
    return value if value > 0 else DEFAULT_AGENT_DAILY_LIMIT


def _today_jst() -> date:
    """現在の JST 日付を返す（日次リセットの境界）。"""
    return datetime.now(timezone.utc).astimezone(JST).date()


def enforce_daily_limit(db: Session, user_id: str, limit: int | None = None) -> int:
    """今日（JST）のリクエスト回数を原子的に増やし、上限超過なら raise する。

    `limit` 未指定時は `resolve_daily_limit()` で env から解決する。
    増加後のカウントが `limit` を超えた場合に `AgentRateLimitExceededError` を raise する
    （limit=N なら N 回目までは許可、N+1 回目で拒否）。commit は呼び出し側の責務。
    """
    if limit is None:
        limit = resolve_daily_limit()

    today = _today_jst()
    count = AgentRateLimitRepository(db, user_id).increment_and_get(today)
    if count > limit:
        raise AgentRateLimitExceededError(limit)
    return count
