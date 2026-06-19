---
paths:
  - backend/**
---

# 認証・暗号化・セキュリティ

## 認証

- **認証方式**: GitHub OAuth のみ。パスワード認証は実装していない（`users` テーブルにパスワード関連カラムは持たない、OAuth 専用設計）
- **JWT**: `python-jose[cryptography]`、RS256 署名（`JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY`）
- **トークン有効期間**:
  - アクセストークン: 15 分（Cookie 名 `access_token`）
  - リフレッシュトークン: 7 日（Cookie 名 `refresh_token`）
- 起動時に `validate_jwt_key_pair()` で秘密鍵と公開鍵の整合性を検証する
- GitHub OAuth の `state` は **backend 側 Cookie で検証**する。web だけで検証しないこと
- 認証 Cookie 属性は `COOKIE_SECURE` / `COOKIE_SAMESITE` で制御する

## 暗号化
- 鍵は `FIELD_ENCRYPTION_KEY` 環境変数（Fernet）

## セキュリティ

- 外部 API 呼び出しのような**高コスト endpoint**には rate limit を付けること（`slowapi`）
- OAuth 開始 URL は backend で発行し、許可された `CORS_ORIGINS` のみをリダイレクト先に使うこと
- Cookie 認証を使う変更では `Secure` / `SameSite` / CORS の整合を必ず確認すること
- Cloudflare Pages → Cloud Run 間は `INTERNAL_SECRET` ヘッダで認証する（local 環境では省略可）
