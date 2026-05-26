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

CLI: OpenTofu (`tofu`) を使用する。Nix で管理されており `nix develop` シェル内で利用可能。`.tf` の構文は Terraform と同一。
デプロイ: GitHub Actions で `dev` ブランチ push 時に frontend → Cloudflare Pages、backend → Docker → Artifact Registry → Cloud Run。

DB は Turso (libSQL) を使用。**DB 本体は OpenTofu の `infra/modules/turso/` で管理**（jpedroh/turso provider）。`module.turso.database_url` を cloud_run module の `turso_database_url` に渡す構成。auth token のみ state に乗せたくないため `turso CLI` で発行 → Secret Manager `<stack_name>-turso-auth-token` に手動投入する運用。詳細は `docs/data-model.md` の「Turso セットアップ」参照。

## 重複・DRY

- 重複検知 / DRY ポリシーは `.claude/rules/common/duplication.md` を参照
- `environments/{dev,stg,prod}` で同じ resource block をコピペしている場合は `modules/` 化を検討する（環境差分は `variable` で吸収）
- `environments/{dev,stg,prod}/{variables,moved,outputs}.tf` は `../shared/<file>.tf` への symlink で物理統合済み。新規ファイルを 3 環境で揃える場合も同じパターンで shared 化し、`.jscpd.json` の ignore に追記する

## monitoring の責務分割

`infra/modules/monitoring/` は責務別にファイル分割している（`notification_channels.tf` / `uptime.tf` / `auth_failures.tf` / `rate_limits.tf` / `task_failures.tf`）。**新規 alert を追加するときは既存ファイルに混ぜず、責務に対応するファイルへ追加するか、新しい責務であれば `monitoring/<新規責務>.tf` を新設する**。1 ファイルに alert を集約すると「監視増→ファイル肥大→責務不明瞭」が再発する。
