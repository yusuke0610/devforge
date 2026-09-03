variable "project_id" {
  description = "GCP project ID。"
  type        = string
}

variable "region" {
  description = "GCP リージョン。Cloud Run サービスのロケーション。"
  type        = string
}

variable "stack_name" {
  description = "Stack 名（{app_name}-{environment}）。サービス名・Secret 名の prefix に使用する。"
  type        = string
}

variable "service_account_email" {
  description = "Cloud Run runtime サービスアカウントのメールアドレス。"
  type        = string
}

variable "enable_github_oauth" {
  description = "GitHub OAuth Secret を Cloud Run に注入するかどうか。"
  type        = bool
  default     = false
}

variable "turso_database_url" {
  description = "Turso (libSQL) データベースの接続 URL（例: libsql://devforge-dev-xxxx.turso.io）。Turso CLI で発行する。"
  type        = string
}

variable "cors_origins" {
  description = "API が許可する CORS origin（カンマ区切り）。"
  type        = string
}

variable "callback_base_url" {
  description = "OAuth callback の base URL（例: https://app.devforge.app）。Cloudflare Pages 経由の redirect_uri を固定するために使用する。未設定の場合は build_external_base_url にフォールバック。"
  type        = string
  default     = ""
}

variable "task_runner" {
  description = "バックグラウンドタスク実行方式 (local / cloud_tasks)。"
  type        = string
  default     = "cloud_tasks"
}

variable "cloud_tasks_queue" {
  description = "Cloud Tasks キュー名。"
  type        = string
  default     = ""
}

variable "cloud_tasks_location" {
  description = "Cloud Tasks キューのロケーション。"
  type        = string
  default     = "asia-northeast1"
}

variable "vertex_anthropic_location" {
  description = "Claude を叩く Vertex AI のロケーション。Tokyo 未提供のため Singapore（ADR-0015）。"
  type        = string
  default     = "asia-southeast1"
  # 空文字は VERTEX_ANTHROPIC_LOCATION="" を注入し backend のデフォルト補完を潰すため弾く
  validation {
    condition     = trimspace(var.vertex_anthropic_location) != ""
    error_message = "vertex_anthropic_location must not be empty."
  }
}

variable "cloud_tasks_service_account" {
  description = "Cloud Tasks OIDC 認証用サービスアカウントメール。"
  type        = string
  default     = ""
}

variable "cloud_tasks_service_url" {
  description = "Cloud Tasks からコールバックする Cloud Run サービス URL。初回 apply 後に設定する。"
  type        = string
  default     = ""
}

variable "environment" {
  description = "実行環境 (dev / stg / prod)。構造化ログの形式制御に使用。"
  type        = string
  default     = "dev"
}

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
