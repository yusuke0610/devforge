output "stack_name" {
  description = "Stack 名（{app_name}-{environment}）。"
  value       = local.stack_name
}

output "artifact_registry_url" {
  description = "Artifact Registry リポジトリ URL（{region}-docker.pkg.dev/{project_id}/{stack_name}）。"
  value       = module.artifact_registry.url
}

output "cloudflare_pages_subdomain" {
  description = "Cloudflare Pages のデフォルトサブドメイン（{project_name}.pages.dev）。"
  value       = module.cloudflare.pages_subdomain
}

output "cloudflare_pages_project_name" {
  description = "Cloudflare Pages プロジェクト名。"
  value       = module.cloudflare.pages_project_name
}

output "service_url" {
  description = "Cloud Run service URL。"
  value       = module.cloud_run.service_url
}

output "turso_database_url" {
  description = "Turso DB の libSQL 接続 URL（backend が TURSO_DATABASE_URL として参照）。"
  value       = module.turso.database_url
}

output "turso_hostname" {
  description = "Turso DB の DNS hostname。"
  value       = module.turso.hostname
}
