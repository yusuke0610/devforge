"""resume_experiences に capital_unit カラムを追加する

資本金の単位（万円 / 百万円 / 千万円 / 億円）を在籍企業ごとに選択できるようにする。
従来は表示時に「千万円」固定だったため、既存行の後方互換として server_default を
「千万円」にする。

libSQL (SQLite 互換) は ALTER COLUMN / DROP COLUMN を直接サポートしないため、
downgrade の列削除は batch_alter_table（テーブル再作成）で行う。ADD COLUMN は
SQLite が直接サポートするため upgrade は op.add_column をそのまま使う。

Revision ID: 0039_add_capital_unit
Revises: 0038_add_project_periods_table
Create Date: 2026-05-29 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039_add_capital_unit"
down_revision: Union[str, None] = "0038_add_project_periods_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resume_experiences",
        sa.Column(
            "capital_unit",
            sa.String(12),
            nullable=False,
            server_default="千万円",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("resume_experiences") as batch_op:
        batch_op.drop_column("capital_unit")
