"""drop billing（credit_transactions / agent_usage_logs / users.credit_balance）

プリペイド課金・使用ログ課金を撤去（ADR-0023 / #522）。abuse 防止は日次レート制限
（#521 / agent_daily_usage）へ移行済み。

- credit_transactions テーブル削除（クレジット台帳）
- agent_usage_logs テーブル削除（使用ログ）
- users.credit_balance カラム削除（残高キャッシュ。libSQL/SQLite 3.35+ は素の
  カラムの直接 DROP COLUMN をサポートするため batch を使わない）

Revision ID: 0051_drop_billing
Revises: 0050_create_agent_daily_usage
Create Date: 2026-07-22 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0051_drop_billing"
down_revision: Union[str, None] = "0050_create_agent_daily_usage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    if _table_exists("credit_transactions"):
        op.drop_table("credit_transactions")
    if _table_exists("agent_usage_logs"):
        op.drop_table("agent_usage_logs")
    op.drop_column("users", "credit_balance")


def downgrade() -> None:
    # 課金は機能撤去のため復元しない（no-op / ADR-0023）。
    # users.credit_balance のみ、スキーマ整合のため復元する。
    op.add_column(
        "users",
        sa.Column("credit_balance", sa.Integer(), nullable=False, server_default="0"),
    )
