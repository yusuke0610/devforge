"""GitHub 連携スキル推論の 3 層テーブルを追加する（ADR-0016 D1）

- github_skills           : Layer 1 / 正規化スキル（language / package）
- github_skill_evidence   : Layer 2 / 技術×リポの根拠（signal_source・量的シグナル）
- github_skill_proficiency: Layer 3 / 習熟度・文脈（本フェーズ未投入）

いずれも新規テーブル作成のみ（op.create_table）で、既存テーブルの再作成は伴わない。
FK は users / github_skills を親に CASCADE 削除。

Revision ID: 0045_add_github_skill_tables
Revises: 0044_add_credit_billing
Create Date: 2026-06-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045_add_github_skill_tables"
down_revision: Union[str, None] = "0044_add_credit_billing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "github_skills",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("ecosystem", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("parent", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
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
            name="uq_github_skills_identity",
        ),
    )
    op.create_index("ix_github_skills_user_id", "github_skills", ["user_id"])

    op.create_table(
        "github_skill_evidence",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "skill_id",
            sa.String(length=36),
            sa.ForeignKey("github_skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repo_full_name", sa.String(length=255), nullable=False),
        sa.Column("repo_url", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("signal_source", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("language_bytes", sa.Integer(), nullable=True),
        sa.Column("dependency_kind", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "skill_id", "repo_full_name", "signal_source",
            name="uq_github_skill_evidence_identity",
        ),
    )
    op.create_index(
        "ix_github_skill_evidence_skill_id", "github_skill_evidence", ["skill_id"]
    )

    op.create_table(
        "github_skill_proficiency",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "skill_id",
            sa.String(length=36),
            sa.ForeignKey("github_skills.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("self_assessed_level", sa.String(length=20), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column("scale", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=True),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default="0"),
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
    op.drop_table("github_skill_proficiency")
    op.drop_index(
        "ix_github_skill_evidence_skill_id", table_name="github_skill_evidence"
    )
    op.drop_table("github_skill_evidence")
    op.drop_index("ix_github_skills_user_id", table_name="github_skills")
    op.drop_table("github_skills")
