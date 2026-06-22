---
paths:
  - backend/**
---

# DB設計ルール

- `basic_info` / `resumes` は **1ユーザー1件** を前提にし、`user_id` を一意制約で縛ること
- 可変長データを JSON カラムへ増やさないこと。資格・学歴・職歴・職務経歴の明細・ブログタグは子テーブルへ正規化すること
- 日付は可能な限り DB の `DATE` / `TIMESTAMP` を使うこと
- `blog_articles` は `account_id` 起点で管理し、`user_id` や `platform` を冗長保持しないこと
- マイグレーション: Alembic（`backend/alembic_migrations/versions/`）。詳細は下記「マイグレーション運用」を参照
- **`IntegrityError` 後の再 SELECT は `None` を判定する**: ユニーク制約衝突後の再取得で、他セッションが先に commit していたケースを想定する。再 SELECT が `None` を返したら明示的に `RuntimeError` を上げ、戻り値型が non-Optional な関数で握りつぶさないこと

## マイグレーション運用

- **ADD COLUMN**: libSQL は `ALTER TABLE ADD COLUMN` を直接サポートするので `op.add_column` をそのまま使う
- **ALTER COLUMN（型・制約変更）**: libSQL は非対応。`batch_alter_table`（テーブル再作成）で行う
- **DROP COLUMN は原則 `op.drop_column` を直接使う**: SQLite/libSQL 3.35+ は `ALTER TABLE ... DROP COLUMN` をサポートする。インデックス・FK・制約のない素のカラムはこれで消せる（テーブル再作成不要）
- **FK 参照される親テーブルに `batch_alter_table` を使わない**: batch は「新テーブル作成 → 旧テーブル DROP → リネーム」で動くため、`users` のように子テーブルから FK 参照される親を batch で触ると、旧テーブル DROP 時に libSQL（`foreign_keys=ON`）で `FOREIGN KEY constraint failed` になる。標準 SQLite ドライバは `foreign_keys` がデフォルト OFF で通ってしまい差異を見落とすので注意。子テーブル（他から参照されない）の `drop_column` でのみ batch は安全
- **マイグレーションは `make test-backend` では検証されない**: テストは `conftest.py` の `Base.metadata.create_all` でスキーマを作るため alembic を通らない。migration の upgrade/downgrade は **実 libSQL に対して**確認すること:
  - offline SQL の事前確認: `nix develop --command bash -c "cd backend && TURSO_DATABASE_URL='file:///tmp/x.db' .venv/bin/python -m alembic upgrade <from>:<to> --sql"`
  - 実適用: docker stack を起動（`make dev-build`）し `docker compose logs api` で適用成功を確認する
- 失敗した `batch_alter_table` が残す `_alembic_tmp_<table>` テーブルは `turso db shell http://localhost:8080 "DROP TABLE IF EXISTS _alembic_tmp_<table>"` で掃除する

## Turso (libSQL) 接続方式

- 接続 URL は `TURSO_DATABASE_URL` 環境変数で指定する。`TURSO_AUTH_TOKEN` は本番では Secret Manager から注入される
- SQLAlchemy 用の URL は `app.core.settings.build_sqlalchemy_database_url()` が以下のように変換する:
  - `http://...` / `https://...` / `libsql://...` → `sqlite+libsql://...?authToken=...`（本番経路: libSQL ドライバ）
  - ローカルファイルパス → `sqlite:///...`（テスト・開発用: 標準 SQLite ドライバ）
- libsql-experimental のローカルファイルドライバは複雑な DDL/DML でロック競合を起こすため、ローカル/テスト用途では標準 SQLite ドライバを使用する。HTTP/HTTPS 接続は別ドライバなので Turso Cloud / turso dev 経路には影響しない
- コネクションプール: HTTP 経由なので `NullPool` を使用（SQLAlchemy のプールは保持しない）
- **ローカル DB**: `backend/local.sqlite` は `turso dev --db-file` で生成する開発用の生成物であり、Git に含めないこと
