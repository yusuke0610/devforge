variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "app_name" {
  description = "Application name prefix."
  type        = string
}

variable "environment" {
  description = "デプロイ環境名。stack_name や Cloud Run の ENVIRONMENT 等に伝播する。dev/stg/prod のいずれか。"
  type        = string

  validation {
    condition     = contains(["dev", "stg", "prod"], var.environment)
    error_message = "environment は dev / stg / prod のいずれかを指定してください。"
  }
}

variable "region" {
  description = "GCP region used by the environment."
  type        = string
  default     = "asia-northeast1"
}

variable "deployer_service_account_email" {
  description = "Optional deployer service account email that needs actAs on the runtime service account."
  type        = string
  default     = ""
}

variable "template_version" {
  description = "Infrastructure template version."
  type        = string
}

variable "cors_origins" {
  description = "Allowed CORS origins for the API."
  type        = string
}

variable "callback_base_url" {
  description = "OAuth callback base URL."
  type        = string
  default     = ""
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token injected via TF_VAR_cloudflare_api_token."
  type        = string
  sensitive   = true
  default     = ""
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID injected via TF_VAR_cloudflare_account_id."
  type        = string
  sensitive   = true
  default     = ""
}

variable "cloudflare_zone_id" {
  description = "Cloudflare DNS zone ID injected via TF_VAR_cloudflare_zone_id."
  type        = string
  sensitive   = true
  default     = ""
}

variable "cloudflare_use_custom_domain" {
  description = "Whether to create a custom-domain CNAME record. false uses only the default *.pages.dev subdomain."
  type        = bool
  default     = false
}

variable "cloudflare_pages_project_name" {
  description = "Cloudflare Pages project name for this environment."
  type        = string
}

variable "cloudflare_subdomain" {
  description = "Cloudflare DNS record name for this environment. Unused when cloudflare_use_custom_domain = false."
  type        = string
  default     = ""
}

variable "cloudflare_production_branch" {
  description = "Cloudflare Pages production branch for this environment."
  type        = string
}

variable "enable_github_oauth" {
  description = "Whether to inject GitHub OAuth secrets into Cloud Run."
  type        = bool
  default     = false
}

variable "enable_extra_llm_providers" {
  description = "Whether to inject Gemini / OpenAI API keys into Cloud Run (ADR-0013). false leaves them uninjected so deploy is not blocked."
  type        = bool
  default     = false
}

variable "alert_email" {
  description = "Monitoring alert destination email."
  type        = string
  sensitive   = true
}

variable "upstash_redis_url" {
  description = "Upstash Redis URL injected via TF_VAR_upstash_redis_url."
  type        = string
  default     = ""
}

variable "upstash_redis_token" {
  description = "Upstash Redis token injected via TF_VAR_upstash_redis_token."
  type        = string
  sensitive   = true
  default     = ""
}

variable "turso_api_token" {
  description = "Turso API token injected via TF_VAR_turso_api_token. provider \"turso\" の api_token に渡す。"
  type        = string
  sensitive   = true
}

variable "turso_organization" {
  description = "Turso organization slug（個人プランは Turso の username）。turso_database リソースの organization_name に渡す。"
  type        = string
}

variable "turso_group" {
  description = "Turso group 名。事前に turso CLI で作成しておく。primary location は group 定義に紐づく。"
  type        = string
  default     = "default"
}
