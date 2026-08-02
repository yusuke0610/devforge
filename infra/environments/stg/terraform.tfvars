project_id       = "devforge-stg-20260404"
app_name         = "devforge"
environment      = "stg"
template_version = "v0.1.0"
# Cloud Run の CORS_ORIGINS / callback_base_url は、この Pages プロジェクト名から
# shared/main.tf の local.frontend_url が導出する（https://<name>.pages.dev）。
cloudflare_pages_project_name  = "devforge-stg"
cloudflare_subdomain           = "app-stg"
cloudflare_production_branch   = "stg"
enable_github_oauth            = true
deployer_service_account_email = "devforge-github-deploy@devforge-stg-20260404.iam.gserviceaccount.com"

# Turso organization slug（個人プランは Turso の username）。実値に置き換えること。
# turso_api_token は機密のため TF_VAR_turso_api_token 環境変数で渡す。
turso_organization = "yusuke0610"
