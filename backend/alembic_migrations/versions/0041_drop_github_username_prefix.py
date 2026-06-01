"""username の "github:" プレフィックスを廃止する

本プロダクトは GitHub ログイン専用のため、username の "github:" 名前空間
プレフィックスは不要。新規保存では付与をやめ、既存行も素の login 名へ書き換える。
GitHub ユーザー判定は username ではなく github_id (unique) で行うよう変更済み。

スキーマ変更はなくデータのみの書き換え。

Revision ID: 0041_drop_github_username_prefix
Revises: 0040_add_resume_non_it_and_vacation
Create Date: 2026-06-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041_drop_github_username_prefix"
down_revision: Union[str, None] = "0040_add_resume_non_it_and_vacation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # "github:" は 7 文字。SQLite SUBSTR は 1 始まりなので 8 文字目以降が素の login 名。
    conn.execute(
        sa.text(
            "UPDATE users SET username = SUBSTR(username, 8) "
            "WHERE username LIKE 'github:%'"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    # GitHub ユーザー（github_id あり）のみプレフィックスを復元する。
    conn.execute(
        sa.text(
            "UPDATE users SET username = 'github:' || username "
            "WHERE github_id IS NOT NULL AND username NOT LIKE 'github:%'"
        )
    )
