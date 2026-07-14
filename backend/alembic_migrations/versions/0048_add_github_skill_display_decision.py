"""スキル表示名の human-in-the-loop 確定テーブルを追加する（ADR-0016 D11）

- github_skill_display_decisions: Layer 3 / agent 提案 → 人間確定の表示名・畳み込みグループ

新規テーブル作成のみ（op.create_table）で、既存テーブルの再作成は伴わない。
Layer 1-2（github_skills / github_skill_evidence）は連携再実行で洗い替えされるが、
本テーブルは安定 identity（kind + ecosystem + canonical_name）をキーに github_skills から
切り離して持つため洗い替えの影響を受けない。FK は users を親に CASCADE 削除。

Revision ID: 0048_add_github_skill_display_decision
Revises: 0047_add_resume_draft_cache_table
Create Date: 2026-07-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0048_add_github_skill_display_decision"
down_revision: Union[str, None] = "0047_add_resume_draft_cache_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "github_skill_display_decisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("ecosystem", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("group_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="human"),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default="1"),
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
        sa.UniqueConstraint(
            "user_id", "kind", "ecosystem", "canonical_name",
            name="uq_github_skill_display_decision_identity",
        ),
    )
    op.create_index(
        "ix_github_skill_display_decisions_user_id",
        "github_skill_display_decisions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_github_skill_display_decisions_user_id",
        table_name="github_skill_display_decisions",
    )
    op.drop_table("github_skill_display_decisions")
