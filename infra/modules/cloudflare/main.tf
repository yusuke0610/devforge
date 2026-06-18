terraform {
  required_providers {
    cloudflare = {
      source = "cloudflare/cloudflare"
    }
  }
}

# Cloudflare Pages プロジェクト
resource "cloudflare_pages_project" "app" {
  account_id        = var.cloudflare_account_id
  name              = var.project_name
  production_branch = var.production_branch
}

# app.<zone> へ CNAME レコードを作成（Cloudflare Proxy 経由）
# use_custom_domain = false の場合はカスタムドメインを使わず、
# Pages のデフォルト *.pages.dev サブドメインのみで運用する（ゾーン未所有でも可）。
resource "cloudflare_record" "app" {
  count = var.use_custom_domain ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = var.subdomain
  type    = "CNAME"
  value   = cloudflare_pages_project.app.subdomain
  proxied = true
}
