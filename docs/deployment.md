# デプロイ・インフラガイド

GCP への本番デプロイ手順、OpenTofu によるインフラ構成、CI/CD、ブランチ保護を扱います。

## 本番デプロイ（GCP）

### 1. 事前準備

```bash
export PROJECT_ID=<your-gcp-project-id>   # 例: devforge-prod-xxxxxxxx
export ENV=<dev|stg|prod>
export REGION=asia-northeast1

# gcloud 認証
gcloud auth login
gcloud config set project ${PROJECT_ID}

# 必要な GCP API を有効化
gcloud services enable artifactregistry.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### 2. OpenTofu でインフラを構築する

CLI は Nix 管理。`nix develop` シェル内で `tofu` を利用する（または `make infra-*` ターゲットを使う）。

```bash
# GCS tfstate バケットを作成（初回のみ）
gcloud storage buckets create gs://devforge-tfstate-${ENV} \
  --location=${REGION} --uniform-bucket-level-access

# インフラ構築
nix develop --command bash -c "cd infra/environments/${ENV} && tofu init && tofu plan && tofu apply"
```

構成: `infra/environments/{dev|stg|prod}`, `infra/modules/`
モジュールの詳細・運用ルール・state 移行については下記「インフラ構成（OpenTofu）」を参照。

### 3. Docker イメージをビルドして push する

> **注意**: Apple Silicon Mac（M1/M2/M3）は必ず `--platform linux/amd64` を付けること。
> 省略すると Cloud Run で `exec format error` が発生する。

```bash
# Docker → Artifact Registry の認証設定（初回のみ）
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# ビルド → タグ付け → push
docker build --platform linux/amd64 -t devforge-${ENV} ./backend
docker tag devforge-${ENV} ${REGION}-docker.pkg.dev/${PROJECT_ID}/devforge-${ENV}/devforge-${ENV}:latest
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/devforge-${ENV}/devforge-${ENV}:latest
```

### 4. Cloud Run にデプロイする

```bash
gcloud run deploy devforge-${ENV} \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/devforge-${ENV}/devforge-${ENV}:latest \
  --region ${REGION} \
  --platform managed

# デプロイ確認（URL取得）
gcloud run services describe devforge-${ENV} --region ${REGION} \
  --format "value(status.url)"
```

秘密情報（`ADMIN_TOKEN` 等）は Secret Manager 経由の環境変数注入を推奨。
GitHub OAuth の `state` は backend 側 Cookie で検証されるため、`CORS_ORIGINS` と Cookie 設定を環境に合わせて揃えること。

### 5. トラブルシューティング

| エラー | 原因 | 対処 |
|---|---|---|
| `Error 403: ... is disabled` | GCP API が未有効 | `gcloud services enable <API名>` |
| `exec format error` | Apple Silicon で `--platform linux/amd64` が未指定 | 上記手順3でビルドし直す |
| `deletion protection is enabled` | OpenTofu destroy 時 | リソースの `deletion_protection = false` に変更 → `apply` → `destroy` |

## インフラ構成（OpenTofu）

GCP インフラストラクチャを OpenTofu で管理しています。CLI は Nix 管理（`nix develop` シェル内で `tofu` が利用可能）。

### ディレクトリ構成

```text
infra/
├── environments/
│   ├── dev/          # 開発環境
│   ├── stg/          # ステージング環境
│   └── prod/         # 本番環境
└── modules/
    ├── artifact_registry/   # Docker イメージリポジトリ
    ├── cloud_run/           # Cloud Run サービス + Secret Manager
    ├── cloud_tasks/         # Cloud Tasks キュー
    ├── cloudflare/          # Cloudflare Pages + DNS
    ├── monitoring/          # Cloud Monitoring アラート
    └── service_account/     # Cloud Run 用サービスアカウント
```

### モジュール

| モジュール | 概要 |
|---|---|
| `service_account` | Cloud Run ランタイム用のサービスアカウント |
| `artifact_registry` | Docker イメージの Artifact Registry リポジトリ |
| `cloud_run` | Cloud Run サービス、Secret Manager シークレット、IAM |
| `cloud_tasks` | バックグラウンドタスク用 Cloud Tasks キュー |
| `cloudflare` | Cloudflare Pages プロジェクトと DNS レコード |
| `monitoring` | Cloud Run エラーレート等のアラート設定 |

> **DB は Turso (libSQL) に移行済み**。GCS の SQLite バックアップ用バケット (`storage` モジュール) は廃止済み。Turso のリソースは OpenTofu 外（`turso CLI` 手動）で管理（[data-model.md](./data-model.md) の「Turso CLI セットアップ」参照）。

### バージョン管理

- OpenTofu 本体: 各環境の `versions.tf` で `required_version` を固定（~> 1.8）
- インフラテンプレート: 各環境の `terraform.tfvars` で `template_version` を管理

### ローカル検証コマンド

```bash
# Makefile 経由（nix develop ラップ済み）
make infra-fmt-check
make infra-validate          # dev / stg / prod をすべて
make infra-validate-dev      # 個別: dev 環境
make infra-validate-stg      # 個別: stg 環境
make infra-validate-prod     # 個別: prod 環境

# 直接実行する場合
nix develop --command tofu -chdir=infra/environments/dev init -backend=false
nix develop --command tofu -chdir=infra/environments/dev validate
```

### plan/apply 実行時の注意

GCS backend を使用しているため、`tofu init` 時にバックエンドの認証が必要です。ローカルで `plan` する場合は `gcloud auth application-default login` を実施してください。

```bash
nix develop --command bash -c "cd infra/environments/dev && tofu init && tofu plan"
```

Cloud Run サービスを OpenTofu で初回作成する場合は、`modules/cloud_run/main.tf` の `local.bootstrap_image` に定義された公開 hello イメージで起動します。Artifact Registry にアプリイメージが push されていなくても初回 apply が成立します。

GitHub Actions はその後 `gcloud run deploy` で新しいリビジョンを配備します。OpenTofu では Cloud Run の `image` 差分を無視するため、後続の `apply` で CI 配備済みイメージへ巻き戻しません。

Secret Manager は secret 本体だけでなく secret version が必要です。Cloud Run 起動前に最低でも以下 4 つの version を追加してください。

- `devforge-<env>-secret-key`
- `devforge-<env>-field-encryption-key`
- `devforge-<env>-admin-token`
- `devforge-<env>-turso-auth-token`

GitHub OAuth を使う場合だけ `enable_github_oauth = true` を設定し、さらに以下 2 つの version も追加してください。

- `devforge-<env>-github-client-id`
- `devforge-<env>-github-client-secret`

DevForge Agent（LLM チャット / ADR-0010・0013）を本番で使う場合は LLM プロバイダの API キーが必要です。Anthropic（Claude）は常に注入され、Gemini / OpenAI は `enable_extra_llm_providers = true` の環境だけ注入されます（未設定なら未注入でデプロイ可能）。

- `devforge-<env>-anthropic-api-key`（Claude haiku / sonnet 用。Agent を使うなら必須）
- `devforge-<env>-google-api-key` / `devforge-<env>-openai-api-key`（`enable_extra_llm_providers = true` のときのみ）

クレジット課金（ADR-0012）で Stripe Checkout を使う場合は以下の version も追加してください。

- `devforge-<env>-stripe-secret-key`
- `devforge-<env>-stripe-webhook-secret`

### 運用ルール

- `dev` → `stg` → `prod` の順で `template_version` を更新
- `main` マージ前に GitHub Actions の `OpenTofu CI` が成功していることを確認

### State 移行（resume_stack からの移行）

各 environment には `moved` ブロックを定義してあり、`module.resume_stack.*` から新しい module address への state 移行は `tofu plan/apply` 時に自動で処理されます。

既に旧構成に対して `apply` を途中まで実行してしまった場合は、最新の設定を反映してから再度 `plan` を実行してください。`resume_stack` 配下の既存 state が残っているリソースは自動で移動され、実際に削除済みのリソースだけが再作成対象として残ります。

### Terraform からの移行メモ

- 本リポジトリは Terraform から OpenTofu に切り替え済み。`.tf` ファイル本体の構文は互換のためそのまま使用可能。
- 旧 `.terraform.lock.hcl` は削除済み。初回 `tofu init` で `registry.opentofu.org` のプロバイダ向けに再生成されます。
- GCS バックエンドの state はそのまま流用できます（破壊的な変換は不要）。

## CI/CD（GitHub Actions）

### アプリケーション CI（`.github/workflows/ci.yml`）

- **実行タイミング**: `pull_request` / `push`（target: `dev` / `stg` / `main`、`frontend/**` or `backend/**` 変更時）
- **テスト内容**:
  - frontend: `npm run lint`, `npm run test`, `npm run build`, E2E（Playwright / Chromium）
  - backend: `ruff check`, `pytest`
- **自動デプロイ**（`dev` ブランチ push 時のみ）:
  - フロントエンド → Cloudflare Pages へデプロイ
  - バックエンド → Artifact Registry へイメージ push → Cloud Run デプロイ
  - GitHub Actions 実行用サービスアカウントには、Cloud Run runtime SA に対する `roles/iam.serviceAccountUser` が必要
- **低コスト運用**: Linuxランナー、依存キャッシュ、`concurrency` で古い実行を自動キャンセル、アプリ差分がない場合は重い処理をスキップ

### OpenTofu 検証 CI（`.github/workflows/opentofu-ci.yml`）

- **実行タイミング**: `pull_request` / `push`（target: `dev` / `stg` / `main`、`infra/**` 変更時）
- **実行内容**:
  - `tofu fmt -check -recursive`
  - `tofu init -backend=false`
  - `tofu validate`

## ブランチ保護

### ローカル（ターミナル）での直コミット/直push防止

```bash
./scripts/setup-git-hooks.sh
```

- `.githooks/pre-commit`: `dev` / `stg` / `main` への直接コミットを拒否
- `.githooks/pre-push`: `dev` / `stg` / `main` への直接pushを拒否

### GitHub 側での強制保護（推奨）

1. GitHub リポジトリの `Settings` -> `Branches` -> `Add branch protection rule`
2. `Branch name pattern` に `dev` を設定
3. 以下を有効化
   - `Require a pull request before merging`
   - `Require status checks to pass before merging`
     - `test`
     - `opentofu-fmt`
     - `opentofu-validate-dev`
     - `opentofu-validate-stg`
     - `opentofu-validate-prod`
4. `stg` と `main` についても同じ設定を追加
5. `Do not allow bypassing the above settings`（利用可能な場合）を有効化
6. 保存
