output "stack_name" {
  value = module.devforge_stack.stack_name
}

output "template_version" {
  value = var.template_version
}

output "artifact_registry_url" {
  value = module.devforge_stack.artifact_registry_url
}

output "cloudflare_pages_subdomain" {
  value = module.devforge_stack.cloudflare_pages_subdomain
}

output "cloudflare_pages_project_name" {
  value = module.devforge_stack.cloudflare_pages_project_name
}

output "turso_database_url" {
  value = module.devforge_stack.turso_database_url
}
