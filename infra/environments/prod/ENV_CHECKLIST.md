# 環境変数チェックリスト（prod）

## 必須変数

| 変数名 | 説明 | dev との差分 | 設定場所 |
|---|---|---|---|
| SQLITE_DB_PATH | SQLiteパス | なし（`/tmp/devforge.sqlite`） | Cloud Run env |
| JWT_PRIVATE_KEY | RS256署名用秘密鍵（PEM形式） | ⚠️ 環境別に生成が必要 | Secret Manager |
| JWT_PUBLIC_KEY | RS256検証用公開鍵（PEM形式） | ⚠️ 環境別に生成が必要 | Secret Manager |
| FIELD_ENCRYPTION_KEY | Fernet鍵（個人情報フィールド暗号化） | ⚠️ 環境別に生成が必要（`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`) | Secret Manager |
| GCS_BUCKET_NAME | DBバックアップ用GCSバケット名 | `devforge-prod-db` | Cloud Run env |
| GCS_DB_OBJECT | GCS上のDBオブジェクトパス | 例: `devforge/prod/db.sqlite` | Cloud Run env |
| ADMIN_TOKEN | `/admin/backup` エンドポイント認証トークン | ⚠️ 環境別に生成が必要 | Secret Manager |
| CORS_ORIGINS | 許可するCORSオリジン | `https://devforge.pages.dev`（`cloudflare_pages_project_name` から自動導出） | Cloud Run env（tofu が設定） |
| COOKIE_SECURE | Secure Cookie フラグ | `true` | Cloud Run env |
| COOKIE_SAMESITE | SameSite Cookie 属性 | `none` | Cloud Run env |

## オプション変数

| 変数名 | 説明 | 推奨値 |
|---|---|---|
| GITHUB_CLIENT_ID | GitHub OAuth Client ID | prod用アプリを別途登録すること |
| GITHUB_CLIENT_SECRET | GitHub OAuth Client Secret | prod用アプリを別途登録すること |

## 手動作業チェックリスト

- [ ] GCPプロジェクト作成（`devforge-prod`）
- [ ] GCSバケット作成（tfstate用: `devforge-tfstate-prod`、DB用: `devforge-prod-db`）
- [ ] デプロイ用サービスアカウント作成（`devforge-github-deploy@devforge-prod.iam.gserviceaccount.com`）
- [ ] `terraform init` 実行（本番適用前）
- [ ] `terraform apply` 実行
- [ ] Secret Manager に必須変数を登録
- [ ] Cloud Run サービスに環境変数を設定
- [ ] GitHub Secrets 登録
  - [ ] `GCP_SA_KEY_PROD`（prodデプロイ用サービスアカウントキーJSON）
  - [ ] `VITE_API_BASE_URL_PROD`（prod Cloud Run サービスURL）
- [ ] Cloudflare Pages プロジェクト設定（`devforge` プロジェクト、prod ブランチを紐付け）
- [ ] GitHub OAuth アプリ登録（prod用コールバックURL設定）
- [ ] prod デプロイ前に stg での動作確認を完了させること
