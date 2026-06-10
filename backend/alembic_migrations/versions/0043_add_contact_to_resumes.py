"""職務経歴書（resumes）に連絡先カラム（email / github_url）を追加する

- resumes に email（メールアドレス・必須運用）と github_url（GitHub URL・任意）を追加。
  既存行は連絡先未入力のため server_default="" で後方互換を保つ（次回フォーム保存時に
  必須バリデーションが効く）。

libSQL (SQLite 互換) は ADD COLUMN を直接サポートするため upgrade は op.add_column を使う。
downgrade の列削除は、resumes が子テーブル（resume_experiences / resume_qualifications）から
FK 参照される親テーブルのため batch_alter_table（テーブル再作成）を使わない。素のカラムは
SQLite/libSQL 3.35+ の ALTER TABLE DROP COLUMN で直接削除できる。

Revision ID: 0043_add_contact_to_resumes
Revises: 0042_drop_users_hashed_password
Create Date: 2026-06-10 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043_add_contact_to_resumes"
down_revision: Union[str, None] = "0042_drop_users_hashed_password"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "resumes",
        sa.Column("email", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "resumes",
        sa.Column("github_url", sa.String(length=255), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("resumes", "github_url")
    op.drop_column("resumes", "email")
