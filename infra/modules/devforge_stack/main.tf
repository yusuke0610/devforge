# --------------------------------------------------------------------
# devforge_stack: environments/<env> から呼ばれる stack composition module
# 6 つの既存 module（service_account / artifact_registry / cloud_tasks /
# cloud_run / monitoring / cloudflare）を内包し、必要な GCP API も
# 同じ場所で有効化する。
# --------------------------------------------------------------------

locals {
  stack_name = "${var.app_name}-${var.environment}"

  # Cloud Run / Cloud Tasks / Artifact Registry / Secret Manager / Monitoring / Logging の依存 API
  required_apis = [
    "artifactregistry.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtasks.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
  ]
}

# 必要な GCP API の有効化（destroy 時には無効化しない）
resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)

  project                    = var.project_id
  service                    = each.value
  disable_on_destroy         = false
  disable_dependent_services = false
}

module "service_account" {
  source = "../service_account"

  project_id                     = var.project_id
  stack_name                     = local.stack_name
  deployer_service_account_email = var.deployer_service_account_email

  depends_on = [google_project_service.apis]
}

module "artifact_registry" {
  source = "../artifact_registry"

  project_id = var.project_id
  region     = var.region
  stack_name = local.stack_name

  depends_on = [google_project_service.apis]
}

module "cloud_tasks" {
  source = "../cloud_tasks"

  project_id  = var.project_id
  app_name    = var.app_name
  environment = var.environment
  location    = var.region

  depends_on = [google_project_service.apis]
}

module "turso" {
  source = "../turso"

  app_name          = var.app_name
  environment       = var.environment
  organization_name = var.turso_organization
  group             = var.turso_group
}

module "cloud_run" {
  source = "../cloud_run"

  project_id                  = var.project_id
  region                      = var.region
  stack_name                  = local.stack_name
  service_account_email       = module.service_account.email
  enable_github_oauth         = var.enable_github_oauth
  turso_database_url          = module.turso.database_url
  cors_origins                = var.cors_origins
  callback_base_url           = var.callback_base_url
  environment                 = var.environment
  task_runner                 = "cloud_tasks"
  cloud_tasks_queue           = module.cloud_tasks.queue_name
  cloud_tasks_location        = var.region
  cloud_tasks_service_account = module.service_account.email
  upstash_redis_url           = var.upstash_redis_url
  upstash_redis_token         = var.upstash_redis_token

  depends_on = [google_project_service.apis]
}

module "monitoring" {
  source = "../monitoring"

  project_id       = var.project_id
  cloud_run_domain = replace(module.cloud_run.service_url, "https://", "")
  alert_email      = var.alert_email

  depends_on = [google_project_service.apis]
}

module "cloudflare" {
  source = "../cloudflare"

  cloudflare_account_id = var.cloudflare_account_id
  cloudflare_zone_id    = var.cloudflare_zone_id
  project_name          = var.cloudflare_pages_project_name
  subdomain             = var.cloudflare_subdomain
  production_branch     = var.cloudflare_production_branch
}
