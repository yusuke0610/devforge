variable "project_id" {
  description = "GCP project ID。"
  type        = string
}

variable "stack_name" {
  description = "Stack 名（{app_name}-{environment}）。サービスアカウント ID の prefix に使用する。"
  type        = string
}

variable "deployer_service_account_email" {
  description = "デプロイ用サービスアカウントのメールアドレス。設定されている場合のみ runtime SA への actAs と Artifact Registry writer / Cloud Run developer ロールを付与する。"
  type        = string
  default     = ""
}
