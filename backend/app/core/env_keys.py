"""環境変数名の SSoT 定義モジュール。

本モジュールは backend / infra / CI / docker-compose を跨いで使われる
環境変数名（文字列リテラル）を Python 定数として集約する。

## SSoT 違反の背景

同じ環境変数名（例: `TURSO_DATABASE_URL`）が以下 4 箇所にリテラルとして
独立に書かれており、rename 時に同期忘れの事故が起きやすい状態だった:

- `backend/app/core/**` の `os.getenv("XXX", ...)`
- `infra/modules/cloud_run/main.tf` の env block
- `.github/workflows/ci.yml` の env / with ブロック
- `docker-compose.yml` の environment ブロック

## 運用ルール

- backend 内では本モジュールの定数を参照する（`os.getenv("XXX")` ではなく `os.getenv(env_keys.XXX)`）
- 新規環境変数を追加する場合は、まず本モジュールに定数を追加する
- 環境変数名を rename する場合:
  1. 本モジュールの定数値を更新
  2. `infra/modules/cloud_run/main.tf` の env block を追従
  3. `.github/workflows/ci.yml` の env / secrets 参照を追従
  4. `docker-compose.yml` の environment ブロックを追従
  5. `docs/api.md` の環境変数表を更新

## drift 検知（自動）

本モジュールの定数値が `docker-compose.yml` の environment にすべて存在するかは
`scripts/lint-env-keys.sh`（`make lint-env-keys` / CI の test-backend ジョブ）で機械検証する。
rename / 追加で compose 追従を忘れると lint が落ちる。ローカル開発で意図的に注入しない
定数（起動時内部フラグ等）は同スクリプトの `COMPOSE_ALLOWLIST` に明示的に追記する。

## 関連ドキュメント

- 環境変数一覧と用途: `docs/api.md`「環境変数」セクション
- インフラでの注入経路: `infra/modules/cloud_run/main.tf`
- ローカル開発での注入経路: `docker-compose.yml`
"""

# --- Turso (libSQL) ---

TURSO_DATABASE_URL = "TURSO_DATABASE_URL"
TURSO_AUTH_TOKEN = "TURSO_AUTH_TOKEN"

# --- 認証 / Cookie / CORS ---

ADMIN_TOKEN = "ADMIN_TOKEN"
JWT_PRIVATE_KEY = "JWT_PRIVATE_KEY"
JWT_PUBLIC_KEY = "JWT_PUBLIC_KEY"
COOKIE_SECURE = "COOKIE_SECURE"
COOKIE_SAMESITE = "COOKIE_SAMESITE"
CORS_ORIGINS = "CORS_ORIGINS"

# --- 暗号化 ---

FIELD_ENCRYPTION_KEY = "FIELD_ENCRYPTION_KEY"

# --- GitHub OAuth ---

GITHUB_CLIENT_ID = "GITHUB_CLIENT_ID"
GITHUB_CLIENT_SECRET = "GITHUB_CLIENT_SECRET"
CALLBACK_BASE_URL = "CALLBACK_BASE_URL"

# --- Cloudflare Pages → Cloud Run 連携 ---

INTERNAL_SECRET = "INTERNAL_SECRET"

# --- アプリケーション識別 ---

APP_VERSION = "APP_VERSION"
ENVIRONMENT = "ENVIRONMENT"

# --- 非同期タスク（Cloud Tasks / Local BackgroundTasks） ---

TASK_RUNNER = "TASK_RUNNER"
GCP_PROJECT_ID = "GCP_PROJECT_ID"
CLOUD_TASKS_QUEUE = "CLOUD_TASKS_QUEUE"
CLOUD_TASKS_LOCATION = "CLOUD_TASKS_LOCATION"
CLOUD_TASKS_SERVICE_URL = "CLOUD_TASKS_SERVICE_URL"
CLOUD_TASKS_SERVICE_ACCOUNT = "CLOUD_TASKS_SERVICE_ACCOUNT"
# タスク最大試行回数。Cloud Tasks キューの retry_config.max_attempts
# （正本: infra/modules/cloud_tasks/main.tf の max_attempts）と一致させること。
# 本番（Cloud Run）の env block には未注入で、既定値 3 で運用している。
# 本番でリトライ上限を変える場合は cloud_tasks 側と本定数の注入を両方更新する。
TASK_MAX_ATTEMPTS = "TASK_MAX_ATTEMPTS"

# --- Upstash Redis ---

UPSTASH_REDIS_URL = "UPSTASH_REDIS_URL"
UPSTASH_REDIS_TOKEN = "UPSTASH_REDIS_TOKEN"

# --- ログ ---

LOG_FORMAT = "LOG_FORMAT"
LOG_LEVEL = "LOG_LEVEL"

# --- LLM（DevForge Agent / ADR-0010・ADR-0013・ADR-0015） ---

# ローカル Ollama 上書き（"1"/"true"/"yes" で有効）。選択モデルに関わらず全リクエストを
# ローカル Ollama に通す無料パス。本番（Cloud Run）では未設定＝無効。
# プロバイダ選択はモデルエイリアスに紐づくため、グローバルな LLM_PROVIDER は廃止（ADR-0013）
LLM_LOCAL_OLLAMA = "LLM_LOCAL_OLLAMA"
# Gemini / Anthropic は Vertex AI（Cloud Run の SA → ADC）経由で叩く（ADR-0015）。
# 認証は SA + GCP_PROJECT_ID（Cloud Tasks と共用）で行い、API キーは持たない。
# ロケーションは provider 別: Gemini=asia-northeast1、Claude=asia-southeast1（Tokyo に
# Claude が無いため）。infra（cloud_run）が plaintext env として注入する。
VERTEX_LOCATION = "VERTEX_LOCATION"
VERTEX_ANTHROPIC_LOCATION = "VERTEX_ANTHROPIC_LOCATION"
# OpenAI のみ GCP に存在しないため API キーを継続使用（ADR-0015）。
# 本番（Cloud Run）では Secret Manager から注入する。ログ出力禁止。
# 注: OPENAI_API_KEY はテストがプロバイダを _FakeLLM でモックするため CI
# （.github/workflows/ci.yml）には注入不要。env_keys の 5 箇所同期のうち ci.yml
# だけは意図的に対象外とする（実 API を CI から呼ばないため）。
OPENAI_API_KEY = "OPENAI_API_KEY"
OLLAMA_BASE_URL = "OLLAMA_BASE_URL"
OLLAMA_MODEL = "OLLAMA_MODEL"
# ローカル Ollama 呼び出しの HTTP タイムアウト秒数（既定 300。ローカル開発専用）
OLLAMA_TIMEOUT_SECONDS = "OLLAMA_TIMEOUT_SECONDS"

# --- 決済（Stripe Checkout / ADR-0012 Phase 2） ---

# 本番（Cloud Run）では Secret Manager から注入する。ログ出力禁止
STRIPE_SECRET_KEY = "STRIPE_SECRET_KEY"
# Webhook 署名検証用シークレット（whsec_...）。ログ出力禁止
STRIPE_WEBHOOK_SECRET = "STRIPE_WEBHOOK_SECRET"

# --- アプリ起動制御 ---

APP_BOOTSTRAPPED = "APP_BOOTSTRAPPED"
