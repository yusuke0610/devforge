"""Agent 日次レート制限のカウンタ永続化（#521 / ADR-0023）。

ユーザ×日ごとの `request_count` を原子的に増やす。Cloud Run 単一インスタンス
（ADR-0005）前提のため分散ロックは不要。IntegrityError（同一キーの競合）は
再取得で吸収する（`.claude/rules/backend/database.md`）。
"""

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AgentDailyUsage


class AgentRateLimitRepository:
    """ユーザ×日の Agent リクエスト回数カウンタ。"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def increment_and_get(self, usage_date: date) -> int:
        """指定日のカウントを 1 増やし、増加後の値を返す（commit はしない）。

        行が無ければ 1 で作成し、あれば ``request_count = request_count + 1`` の
        原子的 UPDATE で増やす。INSERT 競合時は UPDATE 経路にフォールバックする。
        """
        existing = self.db.execute(
            select(AgentDailyUsage).where(
                AgentDailyUsage.user_id == self.user_id,
                AgentDailyUsage.usage_date == usage_date,
            )
        ).scalar_one_or_none()

        if existing is None:
            row = AgentDailyUsage(
                user_id=self.user_id, usage_date=usage_date, request_count=1
            )
            self.db.add(row)
            try:
                self.db.flush()
                return 1
            except IntegrityError:
                # 別リクエストが同一キーを先に作成した場合は UPDATE 経路へ
                self.db.rollback()

        self.db.execute(
            update(AgentDailyUsage)
            .where(
                AgentDailyUsage.user_id == self.user_id,
                AgentDailyUsage.usage_date == usage_date,
            )
            .values(request_count=AgentDailyUsage.request_count + 1)
        )
        self.db.flush()
        count = self.db.execute(
            select(AgentDailyUsage.request_count).where(
                AgentDailyUsage.user_id == self.user_id,
                AgentDailyUsage.usage_date == usage_date,
            )
        ).scalar_one_or_none()
        if count is None:
            # 直前に増やした行が消えるのは想定外。握りつぶさず明示的に失敗させる。
            raise RuntimeError(
                f"agent_daily_usage の再取得に失敗: user_id={self.user_id} date={usage_date}"
            )
        return count
