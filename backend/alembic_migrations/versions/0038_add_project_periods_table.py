"""resume_project_periods テーブルを追加し、プロジェクトの複数期間に対応する

ResumeProject の start_date / end_date / is_current を子テーブル
resume_project_periods に正規化して移す。これにより 1 案件で
「2024/01〜2024/12、2025/06〜現在」のような複数の在籍期間を持てるようになる。

既存データは 1 行 1 期間として resume_project_periods に移行する。

libSQL (SQLite 互換) は ALTER COLUMN / DROP COLUMN を直接サポートしないため
batch_alter_table（テーブル再作成）でカラムを削除する。

Revision ID: 0038_add_project_periods_table
Revises: 0037_merge_project_caf_into_description
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038_add_project_periods_table"
down_revision: Union[str, None] = "0037_merge_project_caf_into_description"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_project_periods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("resume_projects.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, default=0),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, default=False),
    )

    # 既存プロジェクトの start_date / end_date / is_current を 1 期間として移行する。
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, start_date, end_date, is_current FROM resume_projects")
    ).fetchall()
    import uuid as _uuid
    for row in rows:
        conn.execute(
            sa.text(
                "INSERT INTO resume_project_periods "
                "(id, project_id, sort_order, start_date, end_date, is_current) "
                "VALUES (:id, :project_id, 0, :start_date, :end_date, :is_current)"
            ),
            {
                "id": str(_uuid.uuid4()),
                "project_id": row[0],
                "start_date": row[1],
                "end_date": row[2],
                "is_current": row[3],
            },
        )

    with op.batch_alter_table("resume_projects") as batch_op:
        batch_op.drop_column("start_date")
        batch_op.drop_column("end_date")
        batch_op.drop_column("is_current")


def downgrade() -> None:
    with op.batch_alter_table("resume_projects") as batch_op:
        batch_op.add_column(
            sa.Column("start_date", sa.Date(), nullable=False, server_default="2000-01-01"),
        )
        batch_op.add_column(
            sa.Column("end_date", sa.Date(), nullable=True),
        )
        batch_op.add_column(
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default="0"),
        )

    # 各プロジェクトの最初の期間（sort_order=0）を resume_projects に書き戻す。
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT project_id, start_date, end_date, is_current "
            "FROM resume_project_periods WHERE sort_order = 0"
        )
    ).fetchall()
    for row in rows:
        conn.execute(
            sa.text(
                "UPDATE resume_projects SET start_date=:sd, end_date=:ed, is_current=:ic "
                "WHERE id=:pid"
            ),
            {"sd": row[1], "ed": row[2], "ic": row[3], "pid": row[0]},
        )

    op.drop_table("resume_project_periods")
