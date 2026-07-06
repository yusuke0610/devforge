"""経歴書ドラフト生成の非同期タスク用キャッシュテーブルを追加する（ADR-0018 / 非同期化）

- resume_draft_cache: ユーザーごとに最新のドラフト生成 1 件（状態 + 生成 payload）を保持する

新規テーブル作成のみ（op.create_table）で、既存テーブルの再作成は伴わない。
FK は users を親に持つ。``resumes`` テーブルとは無関係（確定した職務経歴書とは別ドメイン）。

Revision ID: 0047_add_resume_draft_cache_table
Revises: 0046_add_manifest_path_to_github_skill_evidence
Create Date: 2026-07-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0047_add_resume_draft_cache_table"
down_revision: Union[str, None] = "0046_add_manifest_path_to_github_skill_evidence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_draft_cache",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="completed"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("resume_draft_cache")
