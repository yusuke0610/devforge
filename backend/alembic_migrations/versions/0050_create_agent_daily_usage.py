"""create agent_daily_usage table（Agent 日次レート制限 / #521・ADR-0023）

プリペイド課金の残高チェックに代わる abuse 防止として、Agent エンドポイントの
ユーザ×日ごとのリクエスト回数を保持する原子的カウンタテーブルを作成する。

Revision ID: 0050_create_agent_daily_usage
Revises: 0049_drop_blog_tables
Create Date: 2026-07-21 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0050_create_agent_daily_usage"
down_revision: Union[str, None] = "0049_drop_blog_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_daily_usage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "usage_date", name="uq_agent_daily_usage_user_date"),
    )


def downgrade() -> None:
    op.drop_table("agent_daily_usage")
