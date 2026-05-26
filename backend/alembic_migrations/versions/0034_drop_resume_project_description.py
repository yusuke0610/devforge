"""drop resume_projects.description (プロジェクト概要の廃止)

プロジェクト概要(description)はプロジェクト名でほぼ内容を踏襲できるため、
入力欄・PDF/Markdown 出力・キャリア分析プロンプトから廃止した。これに伴い
resume_projects.description カラムを削除する。

libSQL (SQLite 互換) は ALTER COLUMN / DROP COLUMN を直接サポートしないため、
batch_alter_table（テーブル再作成）でカラムを落とす。

Revision ID: 0034_drop_resume_project_description
Revises: 0033_drop_resume_imports
Create Date: 2026-05-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0034_drop_resume_project_description"
down_revision: Union[str, None] = "0033_drop_resume_imports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("resume_projects") as batch_op:
        batch_op.drop_column("description")


def downgrade() -> None:
    with op.batch_alter_table("resume_projects") as batch_op:
        batch_op.add_column(
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
        )
