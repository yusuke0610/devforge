"""複数 router から使う共通ヘルパー（router 層専用。HTTP 知識を含むため service には置けない）。"""

from sqlalchemy.orm import Session

from ..core.errors import ErrorCode, raise_app_error
from ..core.messages import get_error
from ..services.agent.rate_limit import AgentRateLimitExceededError, enforce_daily_limit


def enforce_agent_daily_limit(db: Session, user_id: str) -> None:
    """Agent の日次利用上限を確認する（#521 / ADR-0023）。

    プリペイド課金（残高）に代わる abuse 防止。今日（JST）のカウントを原子的に増やし、
    上限超過なら 429 を返す。拒否時もカウントは確定させ、連続試行を含めて数える。
    ``routers/agent.py``（chat / resume-draft / resume-import）と
    ``routers/github_link/endpoints.py``（スキル表示名提案）の両方から呼ばれる共通処理。
    """
    try:
        enforce_daily_limit(db, user_id)
        db.commit()
    except AgentRateLimitExceededError:
        db.commit()
        raise_app_error(
            status_code=429,
            code=ErrorCode.AGENT_DAILY_LIMIT_EXCEEDED,
            message=get_error("agent.daily_limit_exceeded"),
        )
