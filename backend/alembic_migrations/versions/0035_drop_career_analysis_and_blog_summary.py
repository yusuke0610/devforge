"""drop career_analyses / blog_summary_cache とアドバイス系カラム（分析機能の廃止）

ユーザーに価値が伝わらない以下の機能を廃止したことに伴うスキーマ整理:
  - キャリア分析（career_analyses テーブル全体）
  - ブログ AI 分析（blog_summary_cache テーブル全体）
  - GitHub 分析のポジションスコア/学習アドバイス
    （github_analysis_cache.position_advice / ai_summary カラム）

libSQL (SQLite 互換) は DROP COLUMN を直接サポートしないため、カラム削除は
batch_alter_table（テーブル再作成）で行う。テーブル削除は存在チェックの上で drop する。

Revision ID: 0035_drop_career_analysis_and_blog_summary
Revises: 0034_drop_resume_project_description
Create Date: 2026-05-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0035_drop_career_analysis_and_blog_summary"
down_revision: Union[str, None] = "0034_drop_resume_project_description"
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
    # GitHub 分析キャッシュからアドバイス系カラムを削除
    with op.batch_alter_table("github_analysis_cache") as batch_op:
        batch_op.drop_column("position_advice")
        batch_op.drop_column("ai_summary")

    # 廃止機能のテーブルを削除
    if _table_exists("blog_summary_cache"):
        op.drop_table("blog_summary_cache")
    if _table_exists("career_analyses"):
        op.drop_table("career_analyses")


def downgrade() -> None:
    # アドバイス系カラムは復元可能（中身は失われる）
    with op.batch_alter_table("github_analysis_cache") as batch_op:
        batch_op.add_column(sa.Column("ai_summary", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("position_advice", sa.Text(), nullable=True))

    # career_analyses / blog_summary_cache は機能廃止のため復元しない（no-op）。
