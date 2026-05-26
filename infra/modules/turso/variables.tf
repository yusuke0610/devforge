variable "app_name" {
  description = "Application name prefix（DB 名の前半に使う、例: devforge）。"
  type        = string
}

variable "environment" {
  description = "環境識別子（DB 名の後半に使う、例: dev / stg / prod）。"
  type        = string
}

variable "organization_name" {
  description = "Turso organization slug（個人プランは Turso の username と一致）。"
  type        = string
}

variable "group" {
  description = "Turso group 名。事前に CLI で作成しておく必要がある。"
  type        = string
  default     = "default"
}
