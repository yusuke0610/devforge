output "email" {
  description = "Cloud Run runtime サービスアカウントのメールアドレス。"
  value       = google_service_account.app.email
}
