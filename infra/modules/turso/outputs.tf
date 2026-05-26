output "database_url" {
  description = "Backend が TURSO_DATABASE_URL として参照する libSQL 接続 URL。"
  value       = "libsql://${turso_database.this.hostname}"
}

output "hostname" {
  description = "Turso DB の DNS hostname（デバッグ・モニタリング表示用）。"
  value       = turso_database.this.hostname
}

output "db_id" {
  description = "Turso DB の UUID。"
  value       = turso_database.this.db_id
}
