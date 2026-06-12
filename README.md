# DevForge

キャリア関連ドキュメント（職務経歴書）の作成・管理。
GitHub活動分析、ブログ連携による発信力を集計
キャリアインテリジェンスを提供するWebアプリケーションです。

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| [docs/development.md](./docs/development.md) | Nix devshell・初回セットアップ・ローカル開発・テスト/リント |
| [docs/deployment.md](./docs/deployment.md) | 本番デプロイ（GCP）・OpenTofu インフラ構成・CI/CD・ブランチ保護 |
| [docs/api.md](./docs/api.md) | REST API 一覧・環境変数リファレンス |
| [docs/data-model.md](./docs/data-model.md) | Turso (libSQL) 運用・Alembic マイグレーション・データ設計 |
| [docs/adr/](./docs/adr/) | アーキテクチャ判断記録（ADR） |
| [docs/runbooks/](./docs/runbooks/) | 運用 Runbook |

## 主な機能

### ドキュメント管理
- **基本情報**: 氏名・記載日・資格の管理
- **職務経歴書**: 職務要約、自己PR、職務経歴、技術スタックの入力とPDF/Markdown出力
- フォーム入力状態を Redux でページ遷移間に保持（入力途中で別ページに移動しても失われない）

### GitHub連携
- GitHub OAuthログインしたユーザーのリポジトリを取得し、使用技術を可視化
- 言語構成・フレームワーク・DevTools・インフラツールを依存関係から検出
- バックグラウンド非同期処理（202 Accepted → ステータスポーリング方式）

### ブログ連携
- **Zenn** / **note** のアカウント連携・記事同期
- 記事メトリクス（タイトル、URL、公開日、いいね数、タグ）の一覧管理
- **ブログスコアリング**: 投稿頻度・反応数・技術記事比率等をもとにスコアを算出

### 通知
- GitHub連携などのバックグラウンドタスクの成功/失敗をサイドバーの通知ベルで通知
- 未読バッジ表示（30秒ポーリング）・ドロップダウンパネルで一覧表示
- 「全て既読」ボタン・パネル外クリックで閉じる

## 技術スタック

| レイヤー | 技術 |
|---|---|
| フロントエンド | React 18, TypeScript, Vite, Redux Toolkit, Recharts, marked |
| バックエンドAPI | Python 3.13, FastAPI, SQLAlchemy, Pydantic |
| データベース | Turso (libSQL / SQLite 互換、`sqlalchemy-libsql`) |
| 認証 | JWT Cookie (python-jose), bcrypt, GitHub OAuth |
| 暗号化 | Fernet（フィールド暗号化） |
| PDF出力 | WeasyPrint（職務経歴書）, ReportLab（分析レポート補助） |
| インフラ | GCP (Cloud Run, Artifact Registry, Secret Manager), Turso, Cloudflare Pages |
| IaC | OpenTofu（モジュール構成、マルチ環境） |
| CI/CD | GitHub Actions |

## クイックスタート

初回セットアップ（`nix develop` / `make setup` / `make generate-keys` / `make dev`）と
CI 相当の一括実行（`make ci`）の手順は [docs/development.md](./docs/development.md) を正本として参照してください。
README にコマンドを再掲すると docs と二重管理になり同期漏れの原因になるため、リンクのみとしています。

## システム構成図

```mermaid
graph TB
    subgraph "ユーザー"
        Browser["ブラウザ"]
    end

    subgraph "GitHub"
        GitHubActions["GitHub Actions<br/>CI/CD"]
        GitHubOAuth["GitHub OAuth"]
        GitHubAPI["GitHub API"]
    end

    subgraph "外部サービス"
        ZennAPI["Zenn API"]
        NoteRSS["note RSS"]
    end

    subgraph "Cloudflare"
        CFPages["Cloudflare Pages<br/>静的サイトホスティング<br/>（React SPA）"]
    end

    subgraph "Turso"
        TursoDB["Turso DB: devforge-{env}<br/>libSQL（nrt リージョン）"]
    end

    subgraph "GCP Project: <PROJECT_ID>"
        subgraph "Cloud Storage"
            TfstateBucket["GCS: devforge-tfstate-{env}<br/>OpenTofu State"]
        end

        subgraph "Cloud Run"
            CloudRun["Cloud Run: devforge-{env}<br/>FastAPI + libSQL クライアント<br/>max_instances=1 / min_instances=0<br/>CPU: 1000m / Memory: 512Mi"]
        end

        subgraph "Artifact Registry"
            AR["devforge-{env}<br/>Docker イメージ"]
        end

        subgraph "Secret Manager"
            Secrets["FIELD_ENCRYPTION_KEY<br/>ADMIN_TOKEN<br/>JWT_PRIVATE_KEY / JWT_PUBLIC_KEY<br/>INTERNAL_SECRET<br/>TURSO_AUTH_TOKEN<br/>GITHUB_CLIENT_ID / GITHUB_CLIENT_SECRET"]
        end

        subgraph "IAM"
            SA["サービスアカウント<br/>devforge-{env}"]
        end
    end

    Browser -->|"HTTPS"| CFPages
    Browser -->|"API リクエスト"| CloudRun
    Browser -->|"OAuth 認証"| GitHubOAuth

    GitHubActions -->|"npm build → deploy"| CFPages
    GitHubActions -->|"docker push"| AR
    GitHubActions -->|"gcloud run deploy"| CloudRun

    CloudRun -->|"libsql HTTPS"| TursoDB
    CloudRun -->|"シークレット取得"| Secrets
    CloudRun -->|"リポジトリ分析"| GitHubAPI
    CloudRun -->|"記事取得"| ZennAPI
    CloudRun -->|"記事取得"| NoteRSS
    AR -->|"イメージ pull"| CloudRun
    SA -->|"実行権限"| CloudRun
    SA -->|"secretAccessor"| Secrets
```
