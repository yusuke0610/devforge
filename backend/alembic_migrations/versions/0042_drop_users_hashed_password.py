"""users.hashed_password カラムを撤去する

本プロダクトは GitHub OAuth 専用でパスワード認証を実装しておらず、
hashed_password は常に NULL のまま読み取られないデッドカラムだった。
保持コストと将来の誤用を避けるためカラムごと削除する。

hashed_password はインデックス・FK・制約のない素のカラムのため、テーブル再作成を
伴わない直接の DROP COLUMN（SQLite/libSQL 3.35+ がサポート）で削除する。
batch_alter_table は users（多数の子テーブルから FK 参照される親）を一旦 DROP する
ため、libSQL の foreign_keys=ON 環境で FOREIGN KEY 制約違反になり使えない。
downgrade は元の nullable カラムを復元する（ADD COLUMN は libSQL も直接サポート）。

Revision ID: 0042_drop_users_hashed_password
Revises: 0041_drop_github_username_prefix
Create Date: 2026-06-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042_drop_users_hashed_password"
down_revision: Union[str, None] = "0041_drop_github_username_prefix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "hashed_password")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
    )
