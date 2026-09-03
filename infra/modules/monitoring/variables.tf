variable "project_id" {
  description = "GCP project ID。"
  type        = string
}

variable "cloud_run_domain" {
  description = "Cloud Run サービスのドメイン（例: devforge-prod-xxxxx.run.app）。"
  type        = string
}

variable "alert_email" {
  description = "アラート通知先メールアドレス。"
  type        = string
}
