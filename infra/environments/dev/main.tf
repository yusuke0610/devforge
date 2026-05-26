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
# dev 環境の stack composition
# 各 module の呼び出しは ../../modules/devforge_stack に集約されている。
# 環境差分（環境名、Cloudflare Pages 設定、production branch）のみここで渡す。
# --------------------------------------------------------------------
module "devforge_stack" {
  source = "../../modules/devforge_stack"

  environment                    = "dev"
  project_id                     = var.project_id
  app_name                       = var.app_name
  template_version               = var.template_version
  region                         = var.region
  deployer_service_account_email = var.deployer_service_account_email

  cors_origins        = var.cors_origins
  callback_base_url   = var.callback_base_url
  enable_github_oauth = var.enable_github_oauth

  alert_email = var.alert_email

  upstash_redis_url   = var.upstash_redis_url
  upstash_redis_token = var.upstash_redis_token

  turso_organization = var.turso_organization
  turso_group        = var.turso_group

  cloudflare_account_id         = var.cloudflare_account_id
  cloudflare_zone_id            = var.cloudflare_zone_id
  cloudflare_pages_project_name = var.cloudflare_pages_project_name
  cloudflare_subdomain          = var.cloudflare_subdomain
  cloudflare_production_branch  = var.cloudflare_production_branch
}
