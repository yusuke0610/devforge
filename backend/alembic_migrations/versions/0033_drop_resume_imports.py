"""drop resume_imports (LLM ベースの PDF インポート廃止)

職務経歴書 PDF インポートは LLM 抽出 + 非同期タスク方式をやめ、
pdfplumber で抽出したブロックをフロントでクリック割り当てする同期方式
（永続化なし）に置き換えた。これに伴い resume_imports テーブルは不要になる。

Revision ID: 0033_drop_resume_imports
Revises: 0032_add_resume_imports
Create Date: 2026-05-24 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0033_drop_resume_imports"
down_revision: Union[str, None] = "0032_add_resume_imports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='resume_imports'")
    )
    if result.fetchone():
        op.drop_table("resume_imports")


def downgrade() -> None:
    # 前リリース段階での機能廃止。LLM ベースのインポートは復元しないため no-op。
    pass
