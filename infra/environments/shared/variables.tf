# --------------------------------------------------------------------
# dev / stg / prod で共有する環境レベルの variable 定義。
# 実体はこのファイルのみで、各 environments/<env>/variables.tf は
# symlink（../shared/variables.tf）。値は各環境の terraform.tfvars で渡す。
#
# ここで受けた値の大半は modules/devforge_stack へそのまま素通しする。
# variable の宣言順・description は devforge_stack/variables.tf と揃えて
# あるため、片方を変えたらもう片方も同じ差分で更新すること。
# --------------------------------------------------------------------

variable "environment" {
  description = "実行環境識別子（dev / stg / prod）。Cloud Run の ENV 値、stack_name の suffix、Cloud Tasks queue 名に使用する。"
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.environment)
    error_message = "environment は dev / stg / prod のいずれかを指定してください。"
  }
}

variable "project_id" {
  description = "GCP プロジェクト ID。"
  type        = string
}

variable "app_name" {
  description = "アプリケーション名 prefix。stack_name は app_name と environment を - で連結して組み立てる（例: devforge-dev）。"
  type        = string
}

variable "region" {
  description = "GCP リージョン。Cloud Run / Artifact Registry / Cloud Tasks すべてで共通利用。"
  type        = string
  default     = "asia-northeast1"
}

variable "template_version" {
  description = "Infrastructure template version（環境 output・ドキュメント用。リソース定義では未使用）。"
  type        = string
}

variable "deployer_service_account_email" {
  description = "デプロイ用サービスアカウントのメールアドレス。設定されている場合のみ runtime SA への actAs と Artifact Registry writer / Cloud Run developer ロールを付与する。"
  type        = string
  default     = ""
}

# --- アプリケーション設定 ---
#
# cors_origins / callback_base_url は variable ではなく main.tf の
# local.frontend_url で cloudflare_pages_project_name から導出する
# （tfvars との二重管理を避けるため）。

variable "enable_github_oauth" {
  description = "GitHub OAuth Secret を Cloud Run に注入するかどうか。"
  type        = bool
  default     = false
}

# --- 外部サービス: 監視 ---

variable "alert_email" {
  description = "監視アラート通知先メールアドレス。"
  type        = string
  sensitive   = true
}

# --- 外部サービス: Upstash Redis ---
#
# 値は TF_VAR_upstash_redis_url / TF_VAR_upstash_redis_token で注入する
# （tfvars には書かない）。

variable "upstash_redis_url" {
  description = "Upstash Redis 接続 URL（rediss://host:port 形式）。未設定の場合は進捗機能を無効化。"
  type        = string
  default     = ""
}

variable "upstash_redis_token" {
  description = "Upstash Redis 認証トークン。"
  type        = string
  sensitive   = true
  default     = ""
}

# --- 外部サービス: Turso ---

variable "turso_api_token" {
  description = "Turso API トークン。provider \"turso\" の api_token に渡す。TF_VAR_turso_api_token で注入する（環境レベルのみ）。"
  type        = string
  sensitive   = true
}

variable "turso_organization" {
  description = "Turso organization slug（個人プランは Turso の username と一致）。turso_database リソースで organization_name に渡す。"
  type        = string
}

variable "turso_group" {
  description = "Turso group 名。事前に CLI で作成しておく必要がある。primary location は group 定義に紐づく。"
  type        = string
  default     = "default"
}

# --- 外部サービス: Cloudflare ---

variable "cloudflare_api_token" {
  description = "Cloudflare API トークン。provider \"cloudflare\" の api_token に渡す。TF_VAR_cloudflare_api_token で注入する（環境レベルのみ）。"
  type        = string
  sensitive   = true
  default     = ""
}

variable "cloudflare_account_id" {
  description = "Cloudflare アカウント ID。"
  type        = string
  sensitive   = true
  default     = ""
}

variable "cloudflare_zone_id" {
  description = "Cloudflare DNS ゾーン ID（devforge.app ドメイン）。"
  type        = string
  sensitive   = true
  default     = ""
}

variable "cloudflare_use_custom_domain" {
  description = "カスタムドメイン（CNAME レコード）を作成するか。false なら Pages のデフォルト *.pages.dev のみで運用する。"
  type        = bool
  default     = false
}

variable "cloudflare_pages_project_name" {
  description = "Cloudflare Pages プロジェクト名（例: devforge-dev / devforge-stg / devforge）。"
  type        = string
}

variable "cloudflare_subdomain" {
  description = "Cloudflare DNS レコード名（例: app-dev / app-stg / app）。{subdomain}.devforge.app となる。cloudflare_use_custom_domain = false なら未使用。"
  type        = string
  default     = ""
}

variable "cloudflare_production_branch" {
  description = "Cloudflare Pages の production branch 名。dev / stg は環境名と同じ、prod は \"main\"。"
  type        = string
}
