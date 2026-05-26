# --------------------------------------------------------------------
# Turso DB リソース定義
# DB 本体のみを管理する（auth token は CLI で発行 → Secret Manager に手動投入）。
# group は事前に turso CLI で作成済みであること。primary location は
# group 単位で決まるため、本モジュールでは指定しない。
# --------------------------------------------------------------------

resource "turso_database" "this" {
  name              = "${var.app_name}-${var.environment}"
  organization_name = var.organization_name
  group             = var.group

  # DB はアプリ唯一のデータ保持リソース。誤った destroy / 再作成でデータ消失を防ぐ。
  # OpenTofu の lifecycle メタ引数はリテラル値のみ許容するため変数化はできない。
  # 意図的な teardown が必要な場合は、本ブロックを一時的に削除して apply するか
  # `tofu state rm` で state から外してから destroy すること。
  lifecycle {
    prevent_destroy = true
  }
}
