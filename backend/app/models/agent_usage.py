"""DevForge Agent の利用状況モデル。

ADR-0023（Haiku 無料一本化）で、プリペイド課金の残高チェックに代わる abuse 防止として
ユーザ単位の日次レート制限を導入する（#521）。本テーブルはユーザ×日ごとのリクエスト回数を
1 行で保持する原子的カウンタ。
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class AgentDailyUsage(Base):
    """Agent エンドポイントのユーザ×日ごとのリクエスト回数（日次レート制限用）。

    `usage_date` は JST 基準の日付。ユーザ×日で 1 行に集約し、`request_count` を
    原子的 UPDATE で増やす（Cloud Run 単一インスタンス前提 / ADR-0005）。
    """

    __tablename__ = "agent_daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_agent_daily_usage_user_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
