# --------------------------------------------------------------------
# dev / stg / prod で共有する環境レベルの output 定義。
# 実体はこのファイルのみで、各 environments/<env>/outputs.tf は
# symlink（../shared/outputs.tf）。
#
# devforge_stack の output のうち、CI / 運用手順から参照するものだけを
# 環境レベルへ再露出する（stack 側の全 output を素通ししない）。
# --------------------------------------------------------------------

output "stack_name" {
  description = "Stack 名（{app_name}-{environment}）。"
  value       = module.devforge_stack.stack_name
}

output "template_version" {
  description = "Infrastructure template version（tfvars で指定した値をそのまま返す）。"
  value       = var.template_version
}

output "artifact_registry_url" {
  description = "Artifact Registry リポジトリ URL。CI の docker push 先。"
  value       = module.devforge_stack.artifact_registry_url
}

output "cloudflare_pages_subdomain" {
  description = "Cloudflare Pages のデフォルトサブドメイン（{project_name}.pages.dev）。フロントエンドの実配信 URL。"
  value       = module.devforge_stack.cloudflare_pages_subdomain
}

output "cloudflare_pages_project_name" {
  description = "Cloudflare Pages プロジェクト名。CI のデプロイ先指定に使用する。"
  value       = module.devforge_stack.cloudflare_pages_project_name
}

output "turso_database_url" {
  description = "Turso DB の libSQL 接続 URL（backend が TURSO_DATABASE_URL として参照）。"
  value       = module.devforge_stack.turso_database_url
}
