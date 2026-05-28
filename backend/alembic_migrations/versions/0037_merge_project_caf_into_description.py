"""merge resume_projects challenge/action/result into description（課題・行動・成果の統合）

プロジェクトの「課題」「行動」「成果」は分割する必要がないため、単一の自由記述欄
「詳細」(description) に統合した。これに伴い resume_projects の challenge / action /
result カラムを削除し、description カラムを新設する。

統合対象の既存本番データは存在しないため、データ移行（3 カラムの連結）は行わない。

libSQL (SQLite 互換) は ALTER COLUMN / DROP COLUMN を直接サポートしないため、
batch_alter_table（テーブル再作成）でカラムを入れ替える。

Revision ID: 0037_merge_project_caf_into_description
Revises: 0036_rename_github_analysis_to_github_link
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "0037_merge_project_caf_into_description"
down_revision: Union[str, None] = "0036_rename_github_analysis_to_github_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        text(
            "SELECT COUNT(*) FROM resume_projects"
            " WHERE challenge != '' OR action != '' OR result != ''"
        )
    )
    count = result.scalar() or 0
    if count > 0:
        raise RuntimeError(
            f"resume_projects に challenge/action/result のデータが {count} 件残っています。"
            "カラム削除前にデータを退避してください。"
        )

    with op.batch_alter_table("resume_projects") as batch_op:
        batch_op.add_column(
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
        )
        batch_op.drop_column("challenge")
        batch_op.drop_column("action")
        batch_op.drop_column("result")


def downgrade() -> None:
    with op.batch_alter_table("resume_projects") as batch_op:
        batch_op.add_column(
            sa.Column("challenge", sa.Text(), nullable=False, server_default=""),
        )
        batch_op.add_column(
            sa.Column("action", sa.Text(), nullable=False, server_default=""),
        )
        batch_op.add_column(
            sa.Column("result", sa.Text(), nullable=False, server_default=""),
        )
        batch_op.drop_column("description")
