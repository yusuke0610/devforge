"""クレジット課金モデル（ADR-0012）。

``credit_transactions`` は付与・消費の全履歴を持つ追記専用の台帳（正本）。
``users.credit_balance`` はそのキャッシュで、台帳と同一トランザクション内で更新する。
``agent_usage_logs`` はモデル別の実トークン使用量の記録（無料モデルも記録する）。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class CreditTransaction(Base):
    """クレジットの付与・消費 1 件分の台帳エントリ（追記専用）。"""

    __tablename__ = "credit_transactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 符号付きの増減量（付与: 正 / 消費: 負）
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # 本トランザクション適用後の残高（監査・デバッグ用のスナップショット）
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    # 種別: consumption（チャット消費）/ admin_grant（管理者付与）/ purchase（Stripe 購入）
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    # Stripe Checkout Session ID。UNIQUE 制約により Webhook 再送時の二重付与を防ぐ
    # （Phase 2 で使用。Phase 1 では常に NULL / ADR-0012）
    stripe_session_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )


class AgentUsageLog(Base):
    """Agent チャット 1 回分の実トークン使用量の記録（コスト分析用）。"""

    __tablename__ = "agent_usage_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # model_catalog.py のエイリアス（haiku / sonnet）
    model_alias: Mapped[str] = mapped_column(String(20), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    # 消費クレジット（無料モデルは 0）
    credit_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
