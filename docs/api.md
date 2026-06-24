# API・環境変数リファレンス

REST API エンドポイント一覧と、バックエンド／フロントエンドで使用する環境変数を扱います。

## API概要

### 認証

認証方式は **GitHub OAuth のみ**（パスワード認証は未実装）。

- `GET /auth/me`: 現在のログインユーザー取得
- `POST /auth/logout`: ログアウト
- `POST /auth/refresh`: リフレッシュトークンでアクセストークンを更新
- `GET /auth/github/login-url`: GitHub OAuth 開始URL取得
- `GET /auth/github/login`: GitHub OAuth 認可URLへリダイレクト
- `GET /auth/github/callback`: GitHub OAuth コールバック（GitHub→backend）
- `POST /auth/github/callback`: 互換用コールバック

### 職務経歴書
- `POST /api/resumes`: 作成（1ユーザー1件。既存時は `409`）
- `PUT /api/resumes/{id}`: 更新
- `DELETE /api/resumes`: 削除
- `GET /api/resumes/latest`: 現在データ取得
- `GET /api/resumes/{id}`: 取得
- `GET /api/resumes/{id}/pdf`: PDFダウンロード
- `GET /api/resumes/{id}/markdown`: Markdownダウンロード

### GitHub連携
- `POST /api/github-link/run`: GitHubリポジトリの取得・技術検出パイプラインを実行（GitHub OAuth必須、202 非同期、レート: 5/分）
- `POST /api/github-link/run/retry`: 失敗した連携タスクの再実行（202 非同期）
- `GET /api/github-link/cache`: キャッシュされた連携結果を取得
- `GET /api/github-link/cache/status`: 連携タスクのステータスをポーリング（軽量）
- `GET /api/github-link/progress`: 連携中の進捗ステップ取得

### ブログ連携
- `GET /api/blog/accounts`: 連携アカウント一覧
- `POST /api/blog/accounts`: アカウント追加（Zenn / note、レート: 10/分）
- `PATCH /api/blog/accounts/{platform}`: 連携アカウントの username 更新(同期状態リセット、レート: 10/分)
- `DELETE /api/blog/accounts/{account_id}`: アカウント削除
- `GET /api/blog/articles`: 記事一覧（プラットフォームでフィルタ可）
- `POST /api/blog/accounts/{account_id}/sync`: 外部プラットフォームから記事同期（レート: 10/分）
- `GET /api/blog/score`: ブログスコア（投稿頻度・反応数・技術記事比率等）を算出
- `GET /api/blog/summary-cache`: キャッシュされたAI要約を取得
- `GET /api/blog/summary-cache/status`: AI要約タスクのステータスをポーリング（軽量）
- `POST /api/blog/summarize`: ブログAI要約を生成（202 非同期、レート: 5/分）
- `POST /api/blog/summarize/retry`: 失敗した要約タスクの再実行（202 非同期）

### AIキャリアパス分析
- `POST /api/career-analysis/generate`: キャリアパス分析を開始（職務経歴書必須、202 非同期、レート: 5/分）
- `POST /api/career-analysis/{id}/retry`: 失敗した分析の再実行（202 非同期）
- `GET /api/career-analysis/`: 分析履歴一覧
- `GET /api/career-analysis/{id}`: 分析結果詳細
- `GET /api/career-analysis/{id}/status`: ステータスをポーリング（軽量）
- `DELETE /api/career-analysis/{id}`: 分析結果削除

### マスタデータ管理
- `GET /api/master-data/qualification`: 資格一覧
- `POST /api/master-data/qualification`: 資格追加（管理者）
- `PUT /api/master-data/qualification/{id}`: 資格更新（管理者）
- `DELETE /api/master-data/qualification/{id}`: 資格削除（管理者）
- `GET /api/master-data/technology-stack`: 技術スタック一覧
- `POST /api/master-data/technology-stack`: 技術スタック追加（管理者）
- `PUT /api/master-data/technology-stack/{id}`: 技術スタック更新（管理者）
- `DELETE /api/master-data/technology-stack/{id}`: 技術スタック削除（管理者）

### 通知
- `GET /api/notifications`: 通知一覧（直近30件）
- `GET /api/notifications/unread-count`: 未読件数
- `PATCH /api/notifications/{id}/read`: 個別既読
- `POST /api/notifications/read-all`: 全て既読

### Agent（LLM チャット / ADR-0010）
- `POST /api/agent/chat`: 選択スコープ（`project` / `experience` / `career_summary` / `self_pr`）の内容とプロンプトをもとに、職務経歴書への差分 operations を返す。DB は更新せず、適用はフロント側でユーザー確認後に既存保存 API を呼ぶ。rate limit 10/min。`model` はマルチプロバイダ（ADR-0013）から選択可能 — 無料: `haiku` / `gemini-flash` / `gpt-mini`、有料（クレジット消費）: `sonnet` / `gemini-pro` / `gpt`。プロバイダはモデルエイリアスに紐づいて切り替わる。有料モデルで残高不足の場合は 402 `INSUFFICIENT_CREDITS`（ADR-0012）

### 課金（プリペイドクレジット / ADR-0012）
- `GET /api/billing/balance`: ログインユーザーのクレジット残高
- `GET /api/billing/transactions`: クレジット台帳履歴（付与・消費、新しい順）
- `GET /api/billing/packs`: 購入可能なクレジットパック一覧（`pricing.py` が正本）
- `GET /api/billing/model-rates`: モデル別の標準消費レート（回数目安用）
- `GET /api/billing/usage-summary`: ログインユーザーのモデル別利用実績サマリ
- `POST /api/billing/checkout`: クレジット購入の Stripe Checkout セッションを作成し決済ページ URL を返す（Phase 2・要ログイン・rate limit）
- `POST /api/billing/webhook`: Stripe Webhook（`checkout.session.completed`）でクレジットを付与（Phase 2・`Stripe-Signature` 署名検証必須・認証ガード無し）
- `POST /api/billing/admin/grant`: ユーザーへのクレジット付与（管理者・`ADMIN_TOKEN` Bearer 認証）

### 内部 API（Cloud Tasks コールバック専用）
- `POST /internal/tasks/{task_type}`: Cloud Tasks からのタスク実行リクエストを受け付ける。`TASK_RUNNER=cloud_tasks` の場合は `X-CloudTasks-QueueName` ヘッダで検証

### その他
- `GET /health`: ヘルスチェック

## 環境変数

ローカル開発では `backend/.env` に設定する（`make generate-keys` で JWT 鍵を生成後に各値を記入）。主要な設定:

### DB・暗号化・認証

| 変数 | 用途 |
|---|---|
| `TURSO_DATABASE_URL` | Turso (libSQL) 接続 URL（ローカル: `http://127.0.0.1:8080` / 本番: `libsql://<db>.turso.io`） |
| `TURSO_AUTH_TOKEN` | Turso 認証トークン（本番は Secret Manager から注入。`turso dev` では空） |
| `JWT_PRIVATE_KEY` | RS256署名用秘密鍵（PEM形式） |
| `JWT_PUBLIC_KEY` | RS256検証用公開鍵（PEM形式） |
| `FIELD_ENCRYPTION_KEY` | Fernet暗号化キー（履歴書の個人情報フィールド用） |
| `ADMIN_TOKEN` | 管理者操作用トークン |

### HTTP・Cookie・CORS

| 変数 | 用途 |
|---|---|
| `CORS_ORIGINS` | 許可するオリジン（カンマ区切り） |
| `COOKIE_SECURE` | 認証Cookieに `Secure` を付与するか（本番: `true`） |
| `COOKIE_SAMESITE` | 認証Cookieの SameSite（`lax` / `strict` / `none`） |
| `INTERNAL_SECRET` | Cloudflare Pages → Cloud Run 間の秘密ヘッダー値（local 環境では省略可） |
| `CALLBACK_BASE_URL` | GitHub OAuth `redirect_uri` のベース URL。未設定時は `x-forwarded-host` から自動検出 |

### GitHub OAuth

| 変数 | 用途 |
|---|---|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | GitHub OAuth クライアント情報 |

### 非同期タスク（Cloud Tasks）

| 変数 | 用途 |
|---|---|
| `TASK_RUNNER` | `cloud_tasks`（本番）/ 未設定（ローカル: BackgroundTasks 直接実行） |
| `GCP_PROJECT_ID` | Cloud Tasks の GCP プロジェクト ID |
| `CLOUD_TASKS_QUEUE` | Cloud Tasks のキュー名 |
| `CLOUD_TASKS_LOCATION` | Cloud Tasks のロケーション（例: `asia-northeast1`） |
| `CLOUD_TASKS_SERVICE_URL` | Cloud Tasks → Cloud Run コールバック先 URL（OIDC audience としても検証） |
| `CLOUD_TASKS_SERVICE_ACCOUNT` | Cloud Tasks 実行用サービスアカウント（OIDC `email` として検証） |
| `TASK_MAX_ATTEMPTS` | タスク最大試行回数（リトライ判定で参照） |

### Redis（レートリミット等）

| 変数 | 用途 |
|---|---|
| `UPSTASH_REDIS_URL` | Upstash Redis REST URL（本番） |
| `UPSTASH_REDIS_TOKEN` | Upstash Redis REST トークン |

### LLM（DevForge Agent / ADR-0010）

| 変数 | 用途 |
|---|---|
| `LLM_LOCAL_OLLAMA` | ローカル Ollama 上書き（`1`/`true`/`yes` で有効）。選択モデルに関わらず全リクエストを Ollama に通す無料パス。本番は未設定＝無効（ADR-0013） |
| `VERTEX_LOCATION` | Gemini を叩く Vertex AI のロケーション（ADR-0015。既定: `asia-northeast1`）。認証は SA→ADC で `GCP_PROJECT_ID` を共用。API キー不要 |
| `VERTEX_ANTHROPIC_LOCATION` | Claude を叩く Vertex AI のロケーション（ADR-0015。既定: `asia-southeast1`。Tokyo 未提供のため Singapore）。regional endpoint は global 比 +10% 課金 |
| `OPENAI_API_KEY` | OpenAI API キー（ADR-0013/0015。GCP に存在しないため唯一キー継続。`enable_extra_llm_providers=true` の環境で Secret Manager `openai-api-key` から注入） |
| `OLLAMA_BASE_URL` | ローカル Ollama のベース URL（既定: `http://localhost:11434`） |
| `OLLAMA_MODEL` | ローカル Ollama のモデル名（既定: `llama3.2`） |
| `OLLAMA_TIMEOUT_SECONDS` | ローカル Ollama 呼び出しの HTTP タイムアウト秒数（既定: `300`） |

### 決済（Stripe Checkout / ADR-0012 Phase 2）

| 変数 | 用途 |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe シークレットキー（本番は Secret Manager `stripe-secret-key` から注入）。未設定なら購入機能は無効（`/api/billing/checkout` が 503） |
| `STRIPE_WEBHOOK_SECRET` | Stripe Webhook 署名シークレット（`whsec_...`、本番は Secret Manager `stripe-webhook-secret` から注入）。`/api/billing/webhook` の署名検証に必須 |

### 運用・ロギング

| 変数 | 用途 |
|---|---|
| `ENVIRONMENT` | 環境名（`local` / `dev` / `stg` / `prod`） |
| `APP_VERSION` | アプリケーションバージョン（ログ・メトリクス用） |
| `LOG_LEVEL` | ログレベル（`DEBUG` / `INFO` / `WARNING` / `ERROR`） |
| `LOG_FORMAT` | ログフォーマット（`json` / `text`） |
| `APP_BOOTSTRAPPED` | `1` 指定で起動時 bootstrap（DB / 鍵検証）をスキップ。マイグレーションを別途流す環境で使用 |

### フロントエンド

| 変数 | 用途 |
|---|---|
| `VITE_API_BASE_URL` | フロントエンド→バックエンドURL |
