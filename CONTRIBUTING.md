# Contributing Guide

## ブランチ戦略

| ブランチ | 用途 |
|---|---|
| `main` | 本番リリース済みコード |
| `develop` | 開発統合ブランチ |
| `feature/*` | 機能開発 |
| `fix/*` | バグ修正 |
| `docs/*` | ドキュメント変更 |
| `refactor/*` | リファクタリング |
| `infra/*` | インフラ変更 |

## PR の作り方

- `develop` ブランチに向けて PR を作成する
- PR タイトルは `: <内容>` の形式（例: `feat: GitHub 連携スコア計算の追加`）
- セルフレビュー後にマージする

## ADR（Architecture Decision Record）

### ADR とは

技術選定・アーキテクチャ上の重要な判断を記録するドキュメントです。
「なぜその技術を選んだか」「どんな代替案を検討したか」「既知のリスクは何か」を残すことで、
将来の自分や開発者が設計意図を理解できるようにします。

### ADR を書くべきタイミング

以下のいずれかに該当する判断を行った場合は ADR を作成してください。

- 新しいライブラリ・サービス・インフラを採用するとき
- 既存の技術スタックを変更・廃止するとき
- セキュリティ・コスト・パフォーマンスに影響するアーキテクチャ判断を行うとき
- 「なぜこうしたのか」を後から説明する必要がありそうな判断をするとき

迷ったら書く。小さすぎる判断に ADR は不要ですが、書きすぎて困ることはありません。

### ファイル命名規則

```
docs/adr/XXXX-kebab-case-title.md
```

- `XXXX` は4桁の連番（例: `0006`）
- タイトルは英語のケバブケース
- テンプレート: `docs/adr/0000-template.md`

### ステータスの運用

| ステータス | 意味 |
|---|---|
| `Proposed` | 提案中・レビュー待ち |
| `Accepted` | 採用済み・現在有効 |
| `Deprecated` | 廃止済み（理由を本文に記載） |
| `Superseded by ADR-XXXX` | 別の ADR に置き換えられた |

### 既存 ADR を更新する場合

既存の判断を覆す場合は既存の ADR を直接編集せず、新しい ADR を作成してください。

1. 新しい ADR を作成し、ステータスを `Accepted` にする
2. 古い ADR のステータスを `Superseded by ADR-XXXX` に変更する
3. 古い ADR の本文末尾に変更の経緯を一行追記する

### 既存の ADR 一覧

| No. | タイトル | ステータス |
|---|---|---|
| [ADR-0001](docs/adr/0001-sqlite-gcs-backup.md) | SQLite + GCS バックアップ方式の採用 | Accepted |
| [ADR-0002](docs/adr/0002-jwt-cookie-auth.md) | JWT + Cookie 認証方式の採用 | Accepted |
| [ADR-0003](docs/adr/0003-redux-toolkit-persist.md) | Redux Toolkit + redux-persist の採用 | Accepted |
| [ADR-0004](docs/adr/0004-llm-provider-abstraction.md) | LLM プロバイダ抽象化（Ollama/Vertex AI） | Superseded by ADR-0008 |
| [ADR-0005](docs/adr/0005-cloudrun-single-instance.md) | Cloud Run single instance 構成の採用 | Accepted |
| [ADR-0006](docs/adr/0006-tanstack-query.md) | TanStack Query 導入検討 | Proposed |
| [ADR-0008](docs/adr/0008-remove-llm-to-rule-based-design.md) | LLM プロバイダ抽象化の撤去とルールベース設計への統一 | Accepted |
