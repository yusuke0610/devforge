locals {
  secret_names = [
    "secret-key",
    "field-encryption-key",
    "admin-token",
    "github-client-id",
    "github-client-secret",
    "jwt-private-key",
    "jwt-public-key",
    "internal-secret",
    "turso-auth-token",
    # DevForge Agent（ADR-0010）の Anthropic API キー
    "anthropic-api-key",
    # 決済（Stripe Checkout / ADR-0012 Phase 2）の API キーと Webhook 署名シークレット
    "stripe-secret-key",
    "stripe-webhook-secret",
    # 棚卸し TODO: "field-encryption-key"（FIELD_ENCRYPTION_KEY / Fernet 鍵）は
    # このリストから除外し対応する Secret Manager シークレットを削除すること。
    # 削除前に全環境（dev/stg/prod）の Cloud Run 設定から環境変数を外すこと。
  ]
  required_secret_env = {
    FIELD_ENCRYPTION_KEY  = "field-encryption-key"
    ADMIN_TOKEN           = "admin-token"
    JWT_PRIVATE_KEY       = "jwt-private-key"
    JWT_PUBLIC_KEY        = "jwt-public-key"
    INTERNAL_SECRET       = "internal-secret"
    TURSO_AUTH_TOKEN      = "turso-auth-token"
    ANTHROPIC_API_KEY     = "anthropic-api-key"
    STRIPE_SECRET_KEY     = "stripe-secret-key"
    STRIPE_WEBHOOK_SECRET = "stripe-webhook-secret"
  }
  github_secret_env = var.enable_github_oauth ? {
    GITHUB_CLIENT_ID     = "github-client-id"
    GITHUB_CLIENT_SECRET = "github-client-secret"
  } : {}

  # 初回 apply 時のブートストラップ用イメージ。
  # AR にアプリイメージが push される前でも Cloud Run リソース作成を成立させるための公開 hello イメージ。
  # 以後は ignore_changes により CI のデプロイが image を上書きする。
  bootstrap_image = "us-docker.pkg.dev/cloudrun/container/hello:latest"
}

resource "google_secret_manager_secret" "app" {
  for_each  = toset(local.secret_names)
  project   = var.project_id
  secret_id = "${var.stack_name}-${each.key}"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "app" {
  for_each  = google_secret_manager_secret.app
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.service_account_email}"
}

resource "google_cloud_run_v2_service" "app" {
  project             = var.project_id
  name                = var.stack_name
  location            = var.region
  deletion_protection = false

  template {
    service_account = var.service_account_email

    containers {
      image = local.bootstrap_image

      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
      ports {
        container_port = 8000
      }

      env {
        name  = "TURSO_DATABASE_URL"
        value = var.turso_database_url
      }
      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }
      env {
        name  = "CALLBACK_BASE_URL"
        value = var.callback_base_url
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name  = "TASK_RUNNER"
        value = var.task_runner
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CLOUD_TASKS_QUEUE"
        value = var.cloud_tasks_queue
      }
      env {
        name  = "CLOUD_TASKS_LOCATION"
        value = var.cloud_tasks_location
      }
      env {
        name  = "CLOUD_TASKS_SERVICE_URL"
        value = var.cloud_tasks_service_url
      }
      env {
        name  = "CLOUD_TASKS_SERVICE_ACCOUNT"
        value = var.cloud_tasks_service_account
      }
      env {
        name  = "UPSTASH_REDIS_URL"
        value = var.upstash_redis_url
      }
      env {
        name  = "UPSTASH_REDIS_TOKEN"
        value = var.upstash_redis_token
      }
      env {
        # Cloud Logging 向け JSON フォーマットを有効化
        name  = "LOG_FORMAT"
        value = "json"
      }
      env {
        # 通常運用は INFO。パフォーマンス分析時のみ DEBUG に変更する
        name  = "LOG_LEVEL"
        value = "INFO"
      }
      env {
        # DevForge Agent（ADR-0010）。本番は Anthropic API（Haiku 4.5）を使用
        name  = "LLM_PROVIDER"
        value = "anthropic"
      }

      dynamic "env" {
        for_each = local.required_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = "latest"
            }
          }
        }
      }

      dynamic "env" {
        for_each = local.github_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app[env.value].secret_id
              version = "latest"
            }
          }
        }
      }
    }

    max_instance_request_concurrency = 80

    scaling {
      max_instance_count = 1
      min_instance_count = 0
    }
  }

  lifecycle {
    # CI deploys new revisions with gcloud run deploy, so Terraform should not
    # try to force the service back to the bootstrap image tag on later applies.
    ignore_changes = [template[0].containers[0].image]
  }
}

resource "google_cloud_run_v2_service_iam_member" "public_access" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
