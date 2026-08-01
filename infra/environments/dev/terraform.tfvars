project_id       = "devforge-dev-20260311"
app_name         = "devforge"
environment      = "dev"
template_version = "v0.1.0"
# フロントの配信元は Cloudflare Pages（cloudflare_pages_project.app）。use_custom_domain は
# 未指定＝false のため、実 URL は <cloudflare_pages_project_name>.pages.dev になる。
# カスタムドメイン（app-dev.<zone>）へ移行する場合は use_custom_domain / cloudflare_zone_id と
# 併せてここも変更すること（この 2 値は Cloud Run の CORS_ORIGINS / callback_base_url に入る）。
cors_origins                   = "https://devforge-dev.pages.dev"
callback_base_url              = "https://devforge-dev.pages.dev"
cloudflare_pages_project_name  = "devforge-dev"
cloudflare_subdomain           = "app-dev"
cloudflare_production_branch   = "dev"
enable_github_oauth            = true
deployer_service_account_email = "devforge-github-deploy@devforge-dev-20260311.iam.gserviceaccount.com"

# Turso organization slug（個人プランは Turso の username）。実値に置き換えること。
# turso_api_token は機密のため TF_VAR_turso_api_token 環境変数で渡す。
turso_organization = "yusuke0610"
