---
paths:
  - infra/**
---

# Infrastructure (OpenTofu)

```
infra/
├── modules/             # cloud_run, artifact_registry, cloud_tasks, cloudflare, monitoring, service_account
└── environments/        # dev, stg, prod（各環境で tfvars 管理）
```

CLI: OpenTofu (`tofu`) を使用する。Nix で管理されており `nix develop` シェル内で利用可能。`.tf` の構文は Terraform と同一。`tofu init` / `plan` / `apply` の具体的な実行手順・GCS backend 認証は `docs/deployment.md`「OpenTofu」セクションを正本として参照（ここでは再掲しない）。
デプロイ: GitHub Actions で `dev` ブランチ push 時に web → Cloudflare Pages、backend → Docker → Artifact Registry → Cloud Run。

DB は Turso (libSQL) を使用。**DB 本体は OpenTofu の `infra/modules/turso/` で管理**（jpedroh/turso provider）。`module.turso.database_url` を cloud_run module の `turso_database_url` に渡す構成。auth token のみ state に乗せたくないため `turso CLI` で発行 → Secret Manager `<stack_name>-turso-auth-token` に手動投入する運用。詳細は `docs/data-model.md` の「Turso セットアップ」参照。

## 記述規約

- `variable` / `output` には必ず `description` を付け、**日本語**で書く（CLAUDE.md のコメント規約に準拠）。値の意味だけでなく「どこに伝播するか」「未設定時にどうなるか」まで書く。`make lint-infra` が機械検証するのは description の存在と日本語文字の有無であり、説明内容の十分性はレビューで確認する
- 名前が `token` / `secret` / `password` / `api_key` / `private_key` を含む variable には `sensitive = true` を付ける（`.claude/rules/security.md`）

description の存在・日本語文字の有無と `sensitive` は `make lint-infra`（`scripts/lint-infra.sh`。`make lint` / `make ci` に含まれる）が機械検証する。`tofu fmt` は整形しか見ず、`tofu validate` は provider の DL が必要でオフラインでは回らないため、その隙間を埋める位置づけ。検証内容と対象外の判断はスクリプト冒頭のコメントが正本。

## 重複・DRY

- 重複検知 / DRY ポリシーは `.claude/rules/common/duplication.md` を参照
- `environments/{dev,stg,prod}` で同じ resource block をコピペしている場合は `modules/` 化を検討する（環境差分は `variable` で吸収）
- `environments/{dev,stg,prod}/{main,variables,moved,outputs,versions}.tf` は `../shared/<file>.tf` への symlink で物理統合済み（環境固有は `backend.tf` と `terraform.tfvars` のみ）。新規ファイルを 3 環境で揃える場合も同じパターンで shared 化し、`.jscpd.json` の ignore に追記する（`make lint-infra` が symlink の有無・向き・ignore 登録を双方向で検証する。環境固有の実ファイルとして許容するのは `backend.tf` と `terraform.tfvars` のみ）
- `environments/shared/variables.tf` と `modules/devforge_stack/variables.tf` は同じ variable を二重宣言する（HCL の module 境界上、避けられない構造的重複）。**宣言順・セクションコメント・description の文言を両者で揃え、片方を変えたらもう片方も同じ差分で更新する**。過去に description が英語/日本語で分裂し、同じ変数の説明が食い違っていた（`make lint-infra` が variable 集合・description・属性・validation の中身・宣言順の一致を検証する。片側専用の variable はスクリプト内の `LAYER_ONLY_ENV` / `LAYER_ONLY_STACK` に追記して除外する）

## monitoring の責務分割

`infra/modules/monitoring/` は責務別にファイル分割している（`notification_channels.tf` / `uptime.tf` / `auth_failures.tf` / `rate_limits.tf` / `task_failures.tf`）。**新規 alert を追加するときは既存ファイルに混ぜず、責務に対応するファイルへ追加するか、新しい責務であれば `monitoring/<新規責務>.tf` を新設する**。1 ファイルに alert を集約すると「監視増→ファイル肥大→責務不明瞭」が再発する。
