"""rename github_analysis_cache -> github_link_cache（GitHub 分析 → GitHub 連携への改名）

「分析していない」実態に合わせて機能名を GitHub 連携に統一したことに伴うスキーマ改名:
  - テーブル github_analysis_cache → github_link_cache
  - カラム analysis_result → result

libSQL (SQLite 互換) は ``ALTER TABLE ... RENAME TO`` をネイティブサポートするため
テーブル改名は op.rename_table で行う。カラム改名は batch_alter_table（テーブル再作成）
で行い、データを保持する。

Revision ID: 0036_rename_github_analysis_to_github_link
Revises: 0035_drop_career_analysis_and_blog_summary
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0036_rename_github_analysis_to_github_link"
down_revision: Union[str, None] = "0035_drop_career_analysis_and_blog_summary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("github_analysis_cache", "github_link_cache")
    with op.batch_alter_table("github_link_cache") as batch_op:
        batch_op.alter_column("analysis_result", new_column_name="result")


def downgrade() -> None:
    with op.batch_alter_table("github_link_cache") as batch_op:
        batch_op.alter_column("result", new_column_name="analysis_result")
    op.rename_table("github_link_cache", "github_analysis_cache")
