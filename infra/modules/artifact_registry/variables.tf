variable "project_id" {
  description = "GCP プロジェクト ID。"
  type        = string
}

variable "region" {
  description = "GCP リージョン。Artifact Registry リポジトリのロケーション。"
  type        = string
}

variable "stack_name" {
  description = "Stack 名（{app_name}-{environment}）。リポジトリ ID にそのまま使用する。"
  type        = string
}
