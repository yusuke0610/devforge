project_id                     = "devforge-dev-20260311"
app_name                       = "devforge"
template_version               = "v0.1.0"
cors_origins                   = "https://devforge-dev-20260311.web.app,https://devforge-dev-20260311.firebaseapp.com"
callback_base_url              = "https://devforge-dev-20260311.web.app"
cloudflare_pages_project_name  = "devforge-dev"
cloudflare_subdomain           = "app-dev"
cloudflare_production_branch   = "dev"
enable_github_oauth            = true
deployer_service_account_email = "devforge-github-deploy@devforge-dev-20260311.iam.gserviceaccount.com"

# Turso organization slug（個人プランは Turso の username）。実値に置き換えること。
# turso_api_token は機密のため TF_VAR_turso_api_token 環境変数で渡す。
turso_organization = "REPLACE_ME"
