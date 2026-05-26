project_id                     = "devforge-prod-20260404"
app_name                       = "devforge"
template_version               = "v0.1.0"
cors_origins                   = "https://devforge-prod.web.app,https://devforge-prod.firebaseapp.com"
callback_base_url              = "https://devforge-prod.web.app"
cloudflare_pages_project_name  = "devforge"
cloudflare_subdomain           = "app"
cloudflare_production_branch   = "main"
enable_github_oauth            = true
deployer_service_account_email = "devforge-github-deploy@devforge-prod-20260404.iam.gserviceaccount.com"

# Turso organization slug（個人プランは Turso の username）。実値に置き換えること。
# turso_api_token は機密のため TF_VAR_turso_api_token 環境変数で渡す。
turso_organization = "REPLACE_ME"
