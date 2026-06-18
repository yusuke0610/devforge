variable "cloudflare_account_id" {
  description = "Cloudflare アカウント ID。"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare DNS ゾーン ID（devforge.app ドメインのゾーン）。use_custom_domain = false の場合は不要。"
  type        = string
  sensitive   = true
  default     = ""
}

variable "use_custom_domain" {
  description = "カスタムドメイン（CNAME レコード）を作成するか。false なら Pages のデフォルト *.pages.dev のみで運用する。"
  type        = bool
  default     = false
}

variable "project_name" {
  description = "Cloudflare Pages プロジェクト名（例: devforge, devforge-dev）。*.pages.dev のサブドメインになる。"
  type        = string
}

variable "subdomain" {
  description = "DNS レコード名（例: app, app-dev）。zone と組み合わせて app.devforge.app のようなカスタムドメインを作成する。"
  type        = string
  default     = "app"
}

variable "production_branch" {
  description = "Cloudflare Pages の本番ブランチ名。"
  type        = string
  default     = "main"
}
