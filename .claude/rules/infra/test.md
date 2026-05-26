---
paths:
  - infra/**
---

# Infra 検証方針（OpenTofu）

Infra 層には実テストフレームワークは存在しない。代わりに **fmt / validate / plan** をテスト相当とみなし、変更時に必ず走らせる。

## いつ検証を回すか（トリガー）

以下のいずれかに該当する変更を行った場合、対応する検証を必ず実行:

- **`infra/modules/**` の変更**: 全環境（dev / stg / prod）の validate が必要（モジュールは全環境から参照される）
- **`infra/environments/<env>/**` の変更**: 当該環境の validate
- **`*.tf` のフォーマット崩れ**: `make infra-fmt-check` が落ちないことを確認
- **新規変数 / outputs 追加**: tfvars との対応関係を確認し、未指定変数で plan が落ちないこと

## 実行コマンド

```bash
make infra-fmt-check       # フォーマットチェック
make infra-validate        # dev / stg / prod を順に validate
make infra-validate-dev    # 個別: dev 環境
make infra-validate-stg    # 個別: stg 環境
make infra-validate-prod   # 個別: prod 環境
```

自動整形:
```bash
make infra-fmt
```

`plan` を手元で確認したい場合（state にアクセスするため認証必要）:
```bash
nix develop --command bash -c "tofu -chdir=infra/environments/dev plan"
```

## OK 基準（達成条件）

以下をすべて満たして初めて「Infra 検証 OK」と判定する:

1. **`make infra-fmt-check` が pass**: 整形済み
2. **`make infra-validate` が pass**: 影響範囲の環境すべてで validate が通る（modules を触ったら 3 環境全て）
3. **plan で意図しないリソース差分が出ない**: 削除・置換（`-/+`）が発生する変更は、本当に意図したものかコミット前に必ず確認する
4. **変数追加時**: 該当環境の `terraform.tfvars` または `*.auto.tfvars` に値を追記したか確認
5. **state を破壊するような変更を避けている**: `lifecycle { prevent_destroy = true }` のリソースに対する破壊的変更が無いこと

## DB（Turso）の扱い

- Turso (libSQL) の DB 本体は OpenTofu の `infra/modules/turso/` で管理（jpedroh/turso provider）
- auth token のみ `turso CLI` で発行 → Secret Manager に手動投入（state 漏洩回避のため Terraform 対象外）
- group は事前に CLI で作成しておく（primary location は group 定義に紐づく）
- スキーマ変更は backend 側の Alembic マイグレーション（`backend/alembic_migrations/versions/`）で行う
- 詳細は `docs/data-model.md` の「Turso セットアップ」参照

## デプロイフロー

GitHub Actions が `dev` ブランチ push 時に自動実行:

1. frontend → Cloudflare Pages
2. backend → Docker → Artifact Registry → Cloud Run

インフラ変更（`infra/**`）は別の GitHub Actions ワークフローまたは手動 `tofu apply` で適用する。

## アンチパターン

- `tofu apply -auto-approve` をローカルから本番に流す
- `lifecycle.prevent_destroy` 付きリソースに対し `terraform_remote_state` 切替で実質再作成する
- modules を変更したのに dev 環境だけで validate して済ます（stg / prod で同じモジュール参照が壊れる）
