"""プリペイドクレジット課金の基盤テーブルを追加する（ADR-0012）

- users.credit_balance: 残高キャッシュ（正本は credit_transactions 台帳）。
  既存行は残高 0 から開始するため server_default="0"
- credit_transactions: 付与・消費の追記専用台帳。stripe_session_id の UNIQUE 制約は
  Phase 2（Stripe Webhook）の二重付与防止用に最初から張る
- agent_usage_logs: Agent チャットの実トークン使用量記録（無料モデル含む）

libSQL (SQLite 互換) は ADD COLUMN を直接サポートするため upgrade は op.add_column を使う。
users は子テーブルから FK 参照される親テーブルのため batch_alter_table（テーブル再作成）を
使わない。素のカラムは SQLite/libSQL 3.35+ の ALTER TABLE DROP COLUMN で直接削除できる。

Revision ID: 0044_add_credit_billing
Revises: 0043_add_contact_to_resumes
Create Date: 2026-06-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044_add_credit_billing"
down_revision: Union[str, None] = "0043_add_contact_to_resumes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "credit_balance", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("transaction_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("stripe_session_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_credit_transactions_user_id", "credit_transactions", ["user_id"]
    )
    op.create_table(
        "agent_usage_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_alias", sa.String(length=20), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("credit_cost", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_usage_logs_user_id", "agent_usage_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_usage_logs_user_id", table_name="agent_usage_logs")
    op.drop_table("agent_usage_logs")
    op.drop_index("ix_credit_transactions_user_id", table_name="credit_transactions")
    op.drop_table("credit_transactions")
    op.drop_column("users", "credit_balance")
