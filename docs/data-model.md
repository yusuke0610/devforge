# データベース・データモデル

Turso (libSQL) の運用、Alembic マイグレーション、テーブル設計方針を扱います。

## データベース・マイグレーション

### Turso (libSQL)

- **本番**: Turso Cloud（東京リージョン `nrt`）。DB 本体は OpenTofu (`infra/modules/turso/`) で作成。auth token のみ `turso CLI` で発行して Secret Manager に登録
- **ローカル**: `turso dev --db-file ./backend/local.sqlite` で libSQL HTTP サーバーを起動
- **接続**: `app.core.settings.build_sqlalchemy_database_url()` が `TURSO_DATABASE_URL` を SQLAlchemy URL（HTTP/HTTPS は `sqlite+libsql://`、ローカルファイルは `sqlite:///`）に変換
- **ローカル DB**: `backend/local.sqlite` はコミットしない。必要時に自動生成/再作成する

### Turso セットアップ（本番）

DB 本体は OpenTofu で宣言し、`tofu apply` で作成します。auth token は state に乗せたくないため、token のみ CLI で発行して Secret Manager に投入します。group は事前に CLI で作成しておく必要があります（primary location は group に紐づく）。

#### 1. 事前準備（CLI、各 organization で 1 回）

```bash
# 認証
turso auth login

# default group を東京リージョンで作成（既に存在する場合はスキップ）
turso group create default --location nrt
```

#### 2. Turso API token と organization slug を設定

`tofu apply` の実行環境（ローカル or GitHub Actions runner）で:

```bash
export TF_VAR_turso_api_token="$(turso auth token)"
```

`infra/environments/<env>/terraform.tfvars` の `turso_organization` を実際の slug に置き換える（個人プランは Turso の username）。

#### 3. OpenTofu で DB を作成

```bash
make infra-validate
nix develop --command bash -c "tofu -chdir=infra/environments/dev apply"
```

`module.devforge_stack.module.turso.turso_database.this` が作成され、output `turso_database_url` に `libsql://devforge-dev-<org>.turso.io` 形式の URL が記録されます。Cloud Run の env block には自動で同じ値が注入されます。

#### 4. auth token を発行して Secret Manager に投入

```bash
# token 発行
TOKEN=$(turso db tokens create devforge-dev)

# Secret Manager の新バージョンとして投入（secret 本体は cloud_run module が作成済み）
printf '%s' "$TOKEN" | gcloud secrets versions add devforge-dev-turso-auth-token \
  --project=<dev project id> --data-file=-
```

stg / prod も同様に実行。Cloud Run は次回 revision 起動時に新 token を読み込みます。

#### 設定マッピング

| 値 | 配置先 |
|---|---|
| `TURSO_DATABASE_URL` | Cloud Run 環境変数（`infra/modules/turso/` の output → cloud_run module が参照） |
| `TURSO_AUTH_TOKEN` | Secret Manager `devforge-<env>-turso-auth-token`（OpenTofu で secret 本体は作成済み、version のみ手動で追加） |
| `TURSO_API_TOKEN` (OpenTofu 実行時) | `TF_VAR_turso_api_token` 環境変数。state には保存されない |

### Alembic マイグレーション

本番環境では Cloud Run 起動時に自動実行される（`alembic upgrade head`）。
手動実行は `make` 経由（Nix devshell ラップ）で行う:

```bash
make migrate                                 # alembic upgrade head
make migrate-create MSG="add user table"     # 新規マイグレーション生成
```

設定: `backend/alembic.ini` / `backend/alembic_migrations/versions`
libSQL は SQLite 互換で ALTER COLUMN 非対応のため、複雑なスキーマ変更は `batch_alter_table` を使う。

## データ設計メモ

- `basic_info` / `resumes` は **1ユーザー1件**
- `career_analyses` は **複数バージョン保持可能**（分析履歴として蓄積）
- `intelligence_cache` / `blog_summary_cache` は **1ユーザー1件**（最新結果のみ保持）
- 可変長データは JSON ではなく子テーブルに正規化
  - `basic_info_qualifications`
  - `resume_experiences` / `resume_clients` / `resume_projects` / `resume_project_*`
  - `blog_article_tags`
- 日付は DB では `DATE` として保持
  - 日単位: `record_date` / `birthday` / `blog_articles.published_at`
  - 月単位: 職務経歴・学歴・職歴は月初日に正規化して保存し、API では `YYYY-MM` で返却
- `blog_articles` は `account_id` 起点で管理し、`platform` は `blog_accounts` から解決
- 非同期タスクはステータスフィールド（`pending` / `running` / `completed` / `failed`）で管理し、フロントエンドはポーリングで結果を取得する
