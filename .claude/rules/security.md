---
paths:
  - backend/**
  - web/**
  - infra/**
---

# セキュリティルール（全領域横断）

このファイルは backend / web / infra すべての領域に適用される横断セキュリティルール。
認証・JWT・Cookie 属性・暗号化・Rate Limit の詳細は `.claude/rules/backend/auth-security.md` を参照し、ここでは重複させない。

---

## 秘密情報管理（Secrets Management）

### Git に含めてはいけないもの

- `.env` / `.env.*` — ローカル開発用環境変数
- `*.pem` / `*.key` — 秘密鍵・証明書
- `*.json` のうち GCP サービスアカウント鍵に該当するもの
- `turso-auth-token` 等の認証トークンをハードコードした設定ファイル

### 環境変数の正本

- **定数名の定義**: `backend/app/core/env_keys.py`
- **用途と注入経路の一覧**: `docs/api.md` の「環境変数」セクション
- **本番注入**: `infra/modules/cloud_run/main.tf` の `env` ブロック（Secret Manager 参照形式）
- **ローカル**: `docker-compose.yml`

backend 内で文字列リテラル `os.getenv("XXX")` を使うことは禁止。`env_keys.XXX` 経由で参照する。

### ログへの秘密情報出力禁止

認証トークン・API キー・パスワード・個人情報（メールアドレス含む）をログに出力しない。
デバッグ目的でも `logger.debug` にこれらを含めないこと。

---

## 入力バリデーション・出力エスケープ

### Backend

- **Pydantic バリデーション必須**: API エンドポイントへの入力はすべて `app/schemas/` の Pydantic モデルで型・制約を検証する。`Any` 型や `dict` 型の素通しは避ける
- **SQL インジェクション防止**: SQLAlchemy ORM / Core のパラメータバインドを使う。文字列連結でクエリを組み立てることは禁止

### Frontend

- **`dangerouslySetInnerHTML` は原則禁止**: 外部コンテンツや動的文字列を `innerHTML` / `dangerouslySetInnerHTML` に渡さない。React の自動エスケープを信頼する
- **外部リンク**: `<a target="_blank">` には必ず `rel="noopener noreferrer"` を付ける（タブナビゲーション攻撃の防止）
- **URL パラメータの扱い**: `window.location.search` 等から取得した値を DOM に直接レンダリングしない。必ず React の `state` / `props` 経由で扱う

---

## Frontend セキュリティ

### トークン管理

- アクセストークン・リフレッシュトークンは `HttpOnly` + `Secure` Cookie で管理する（詳細: `.claude/rules/backend/auth-security.md`）
- `localStorage` / `sessionStorage` にトークンを保存しない（XSS で盗取されるリスク）
- Redux の `store` にも生のトークン文字列を乗せない

### XSS 対策まとめ

1. `dangerouslySetInnerHTML` 禁止（上述）
2. Markdown レンダラー等を使う場合は sanitize オプションを有効化する
3. `eval()` / `Function()` コンストラクタの使用禁止

### 依存関係

- `npm audit` で High / Critical CVE が検出された場合は PR マージ前に対処する
- CI が `npm audit --audit-level=high` で落ちた場合は、`--force` で無視せず脆弱なパッケージを更新すること

---

## Backend セキュリティ（追加事項）

認証・JWT・Rate Limit・CORS・INTERNAL_SECRET については `.claude/rules/backend/auth-security.md` を参照。

### ファイルアップロード

ファイルアップロード機能を追加する場合は以下をすべて実装する:

1. **MIME タイプ検証**: `Content-Type` ヘッダだけでなくファイルのバイト列（magic bytes）で検証する
2. **ファイルサイズ上限**: エンドポイント側で上限を設け、OOM を防ぐ
3. **ファイル名サニタイズ**: パストラバーサル（`../` 等）を除去する。UUIDv4 でリネームするのが最もシンプル
4. **保存先**: 本番ではローカルファイルシステムに保存せず GCS 等の外部ストレージを使う

### 依存関係

- `pip audit` / `safety` で定期的に CVE チェックを行う
- CI に `pip-audit` を組み込むことを推奨（High 以上を fail 条件にする）

---

## Infra セキュリティ

### IAM 最小権限

- Cloud Run のサービスアカウントには必要最小限のロールのみ付与する（`infra/modules/service_account/`）
- 新規ロールを付与する際は「なぜそのロールが必要か」をコメントで残す
- `roles/owner` / `roles/editor` 等の広範なロールを Cloud Run SA に付与しない

### Secret Manager

- DB 接続 URL・API キー・JWT 秘密鍵等はすべて Secret Manager に格納し、Cloud Run の `secretEnv` / `secretVolume` 経由で注入する
- Terraform state に平文のシークレットが乗らないよう、`sensitive = true` を必ず付与する
- Turso auth token: state 漏洩防止のため `turso CLI` で発行 → Secret Manager に手動投入（詳細: `.claude/rules/infra/opentofu.md`）

### デプロイ制限

- `tofu apply -auto-approve` をローカルから本番環境に直接流さない（詳細: `.claude/rules/infra/test.md`）
- `lifecycle { prevent_destroy = true }` 付きリソースへの破壊的変更は実行前に必ず確認する

---

## セキュリティレビューチェックリスト

AI エージェントがコードを変更した後に確認する項目:

- [ ] 秘密情報（トークン・キー・パスワード）が Git に含まれていないか
- [ ] 環境変数を文字列リテラルで直接参照していないか（`env_keys.XXX` 経由か）
- [ ] 入力バリデーションが境界（API エンドポイント・フォーム）で行われているか
- [ ] `dangerouslySetInnerHTML` / `innerHTML` の新規使用がないか
- [ ] ログに個人情報・認証情報が出力されないか
- [ ] 新規エンドポイントに認証ガード（`get_current_user` 依存）が付いているか
- [ ] 高コスト処理（外部 API 呼び出し等）に rate limit があるか（`slowapi`）
- [ ] `target="_blank"` に `rel="noopener noreferrer"` が付いているか
- [ ] 新規 IAM ロール付与に最小権限の原則を守っているか
