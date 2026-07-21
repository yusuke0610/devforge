"""drop blog_accounts / blog_articles / blog_article_tags（ブログ連携機能の撤去）

ブログ連携（Zenn / note 同期・記事一覧・投稿スコアリング）は経歴書へ還流せず、
投稿頻度スコアがブランクのあるユーザに逆効果になり得るため撤去する（ADR-0022 / #519）。

FK 依存の順（子 → 親）でテーブルを削除する:
  blog_article_tags → blog_articles → blog_accounts
libSQL は foreign_keys=ON のため、親（blog_accounts / blog_articles）を先に
落とすと子からの FK 参照で失敗する。存在チェックの上で子から順に drop する。

Revision ID: 0049_drop_blog_tables
Revises: 0048_add_github_skill_display_decision
Create Date: 2026-07-21 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0049_drop_blog_tables"
down_revision: Union[str, None] = "0048_add_github_skill_display_decision"
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
    # 子テーブルから順に削除する（FK 依存: tags → articles → accounts）
    if _table_exists("blog_article_tags"):
        op.drop_table("blog_article_tags")
    if _table_exists("blog_articles"):
        op.drop_table("blog_articles")
    if _table_exists("blog_accounts"):
        op.drop_table("blog_accounts")


def downgrade() -> None:
    # ブログ連携は機能撤去のため復元しない（no-op / ADR-0022）。
    # 再導入時は本 ADR を Superseded とした新規 ADR とマイグレーションで作り直す。
    pass
