---
paths:
  - backend/**
---

# DB設計ルール

- `basic_info` / `resumes` は **1ユーザー1件** を前提にし、`user_id` を一意制約で縛ること
- 可変長データを JSON カラムへ増やさないこと。資格・学歴・職歴・職務経歴の明細・ブログタグは子テーブルへ正規化すること
- 日付は可能な限り DB の `DATE` / `TIMESTAMP` を使うこと
- `blog_articles` は `account_id` 起点で管理し、`user_id` や `platform` を冗長保持しないこと
- マイグレーション: Alembic（`backend/alembic_migrations/versions/`）。libSQL は SQLite 互換で ALTER COLUMN 非対応のため `batch_alter_table` を使うこと

## Turso (libSQL) 接続方式

- 接続 URL は `TURSO_DATABASE_URL` 環境変数で指定する。`TURSO_AUTH_TOKEN` は本番では Secret Manager から注入される
- SQLAlchemy 用の URL は `app.core.settings.build_sqlalchemy_database_url()` が以下のように変換する:
  - `http://...` / `https://...` / `libsql://...` → `sqlite+libsql://...?authToken=...`（本番経路: libSQL ドライバ）
  - ローカルファイルパス → `sqlite:///...`（テスト・開発用: 標準 SQLite ドライバ）
- libsql-experimental のローカルファイルドライバは複雑な DDL/DML でロック競合を起こすため、ローカル/テスト用途では標準 SQLite ドライバを使用する。HTTP/HTTPS 接続は別ドライバなので Turso Cloud / turso dev 経路には影響しない
- コネクションプール: HTTP 経由なので `NullPool` を使用（SQLAlchemy のプールは保持しない）
- **ローカル DB**: `backend/local.sqlite` は `turso dev --db-file` で生成する開発用の生成物であり、Git に含めないこと
