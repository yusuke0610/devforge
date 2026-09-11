output "repository_id" {
  description = "Artifact Registry リポジトリ ID。"
  value       = google_artifact_registry_repository.app.repository_id
}

output "url" {
  description = "Artifact Registry リポジトリ URL（{location}-docker.pkg.dev/{project_id}/{repository_id}）。"
  value       = "${google_artifact_registry_repository.app.location}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}
