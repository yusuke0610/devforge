"""非IT経歴フラグ・詳細と休暇エントリのカラムを追加する

- resume_experiences に is_it_company（IT企業かどうか）と description（非IT時の詳細）を追加。
  既存行は IT 企業前提だったため is_it_company の server_default を True(1) にする。
- resume_clients に is_vacation（休暇エントリか）と vacation_* 期間/詳細を追加。
  既存行は通常の取引先のため is_vacation の server_default を False(0) にする。

libSQL (SQLite 互換) は ADD COLUMN を直接サポートするため upgrade は op.add_column を
そのまま使う。downgrade の列削除は ALTER/DROP COLUMN 非対応のため batch_alter_table
（テーブル再作成）で行う。

Revision ID: 0040_add_resume_non_it_and_vacation
Revises: 0039_add_capital_unit
Create Date: 2026-05-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_add_resume_non_it_and_vacation"
down_revision: Union[str, None] = "0039_add_capital_unit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resume_experiences",
        sa.Column("is_it_company", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "resume_experiences",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "resume_clients",
        sa.Column("is_vacation", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "resume_clients",
        sa.Column("vacation_start_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "resume_clients",
        sa.Column("vacation_end_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "resume_clients",
        sa.Column("vacation_is_current", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "resume_clients",
        sa.Column("vacation_description", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    with op.batch_alter_table("resume_clients") as batch_op:
        batch_op.drop_column("vacation_description")
        batch_op.drop_column("vacation_is_current")
        batch_op.drop_column("vacation_end_date")
        batch_op.drop_column("vacation_start_date")
        batch_op.drop_column("is_vacation")
    with op.batch_alter_table("resume_experiences") as batch_op:
        batch_op.drop_column("description")
        batch_op.drop_column("is_it_company")
