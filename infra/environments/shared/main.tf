provider "google" {
  project = var.project_id
  region  = var.region
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

provider "turso" {
  api_token = var.turso_api_token
}

# --------------------------------------------------------------------
# フロントエンドの配信 URL（CORS_ORIGINS / OAuth コールバックの導出元）
#
# 配信元は Cloudflare Pages（cloudflare_pages_project.app）。
# cloudflare_use_custom_domain は全環境 false のため、実 URL は Pages の
# デフォルトサブドメイン <cloudflare_pages_project_name>.pages.dev になる。
# tfvars に URL をベタ書きすると Pages プロジェクト名との二重管理になり、
# 改名時に CORS と OAuth コールバックが同時に壊れるため、ここで導出する。
#
# カスタムドメイン（app-dev.<zone> 等）へ移行する場合は、
# cloudflare_use_custom_domain / cloudflare_zone_id の指定と併せて
# この local を分岐させること（cloudflare_subdomain がホスト名側になる）。
# --------------------------------------------------------------------
locals {
  frontend_url = "https://${var.cloudflare_pages_project_name}.pages.dev"
}

# --------------------------------------------------------------------
# stack composition（全環境共通）
# 各 module の呼び出しは ../../modules/devforge_stack に集約されている。
# 環境差分は terraform.tfvars 経由（environment / Cloudflare Pages 設定 /
# production branch 等）で渡し、この main.tf 自体は全環境で共有する。
# --------------------------------------------------------------------
module "devforge_stack" {
  source = "../../modules/devforge_stack"

  environment                    = var.environment
  project_id                     = var.project_id
  app_name                       = var.app_name
  template_version               = var.template_version
  region                         = var.region
  deployer_service_account_email = var.deployer_service_account_email

  cors_origins        = local.frontend_url
  callback_base_url   = local.frontend_url
  enable_github_oauth = var.enable_github_oauth

  alert_email = var.alert_email

  upstash_redis_url   = var.upstash_redis_url
  upstash_redis_token = var.upstash_redis_token

  turso_organization = var.turso_organization
  turso_group        = var.turso_group

  cloudflare_account_id         = var.cloudflare_account_id
  cloudflare_zone_id            = var.cloudflare_zone_id
  cloudflare_use_custom_domain  = var.cloudflare_use_custom_domain
  cloudflare_pages_project_name = var.cloudflare_pages_project_name
  cloudflare_subdomain          = var.cloudflare_subdomain
  cloudflare_production_branch  = var.cloudflare_production_branch
}
