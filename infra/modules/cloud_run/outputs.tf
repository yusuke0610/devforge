output "service_url" {
  description = "Cloud Run サービスの URL。"
  value       = google_cloud_run_v2_service.app.uri
}
