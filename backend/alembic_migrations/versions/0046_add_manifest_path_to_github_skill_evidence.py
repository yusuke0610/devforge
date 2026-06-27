"""github_skill_evidence に manifest_path / partial_scan を追加する（ADR-0016 D9）

monorepo サブツリー探索（D9）で検出した manifest の相対パス（証跡 / D9(f)）と、
走査が網羅でない部分スキャンだったか（D9(d)）を Layer 2 根拠に保持する。

子テーブル（他から FK 参照されない）への素の ADD COLUMN のみ。libSQL は
``ALTER TABLE ADD COLUMN`` を直接サポートするため ``batch_alter_table`` は使わない。

Revision ID: 0046_add_manifest_path_to_github_skill_evidence
Revises: 0045_add_github_skill_tables
Create Date: 2026-06-26 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046_add_manifest_path_to_github_skill_evidence"
down_revision: Union[str, None] = "0045_add_github_skill_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "github_skill_evidence",
        sa.Column("manifest_path", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "github_skill_evidence",
        sa.Column(
            "partial_scan", sa.Boolean(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("github_skill_evidence", "partial_scan")
    op.drop_column("github_skill_evidence", "manifest_path")
