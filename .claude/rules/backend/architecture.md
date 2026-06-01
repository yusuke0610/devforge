---
paths:
  - backend/**
---

# Backend アーキテクチャ (FastAPI)

```
backend/app/
├── main.py              # FastAPI アプリ（lifespan で DB bootstrap・鍵検証）
├── messages.json        # ユーザー向けメッセージ・通知文言の定義
├── core/                # 設定・メッセージ・認証・暗号化などの横断基盤
│   ├── settings.py
│   ├── env_keys.py      # 環境変数名の定数定義（正本）
│   ├── messages.py
│   ├── logging_utils.py
│   ├── date_utils.py
│   ├── encryption.py
│   ├── errors.py        # ErrorCode / raise_app_error
│   ├── context.py       # リクエスト相関 ID 等のコンテキスト
│   ├── metrics.py
│   ├── redis_client.py
│   └── security/
│       ├── auth.py      # JWT（RS256）発行・検証
│       ├── csrf.py
│       └── dependencies.py
├── middleware/
│   └── request_id.py    # リクエスト ID 付与
├── db/                  # DB 接続・bootstrap・migration 補助
│   ├── database.py
│   ├── bootstrap.py
│   ├── migrations.py
│   ├── seed.py
│   └── seeds/
├── routers/             # FastAPI エンドポイント
│   ├── auth/            # 認証関連（endpoints, github_auth, oauth_flow, token_manager）
│   ├── blog/            # ブログ連携（accounts, score, sync）
│   ├── download_utils.py
│   ├── health.py
│   ├── github_link.py
│   ├── internal.py      # Cloud Tasks → backend 内部 API
│   ├── master_data.py
│   ├── notifications.py
│   └── resumes.py
├── models/              # SQLAlchemy 2.0 宣言的マッピング
│   ├── user.py / blog.py / cache.py
│   ├── master_data.py / notification.py / resume.py
├── schemas/             # Pydantic リクエスト/レスポンススキーマ
│   ├── auth.py / blog.py / github_link.py
│   ├── master_data.py / resume.py / shared.py
├── repositories/        # データアクセス層
│   ├── base.py / user.py / blog.py
│   ├── master_data.py / notification.py / resume.py
├── services/
│   ├── blog/                    # ブログ収集・技術記事判定・スコア算出
│   │   ├── account_service.py
│   │   ├── collector.py
│   │   ├── scorer.py
│   │   ├── sync_service.py
│   │   └── tech_keywords.json
│   ├── intelligence/            # GitHub 連携パイプライン（決定論的・ルールベース）
│   │   ├── pipeline.py
│   │   ├── github_collector.py
│   │   ├── github_link_service.py
│   │   ├── github/              # GitHub API クライアント・リポジトリ解析
│   │   │   ├── api_client.py
│   │   │   └── repo_analyzer.py
│   │   ├── response_mapper.py
│   │   ├── skill_extractor.py
│   │   └── skill_taxonomy/      # スキル分類（言語・トピック・キーワードマップ）
│   ├── tasks/                   # 非同期タスク基盤（Cloud Tasks / ローカル）
│   │   ├── base.py              # TaskType 定義（現状 GITHUB_LINK のみ）
│   │   ├── exceptions.py        # RetryableError / NonRetryableError
│   │   ├── worker.py            # execute_task（状態遷移・通知）
│   │   ├── dispatch_service.py  # AsyncTaskCacheService（状態遷移 + ディスパッチ）
│   │   ├── factory.py
│   │   ├── cloud_tasks.py       # Cloud Tasks エンキュー
│   │   ├── local.py             # BackgroundTasks 直接実行
│   │   └── handlers/            # タスク種別ごとのハンドラ
│   │       ├── base.py          # TaskHandler 抽象基底クラス
│   │       └── github_link.py
│   ├── markdown/                # Markdown 生成（generators / templates / utils）
│   ├── pdf/                     # WeasyPrint による PDF 生成（generators / utils）
│   ├── progress_service.py      # 進捗状態管理
│   └── shared/                  # ドメイン横断の service util
│       ├── resume_format.py     # レジュメ整形の共通ロジック（md/pdf 共有）
│       └── sort_utils.py
├── fonts/               # PDF 生成用フォント
└── utils/
```

## 主要モジュールのポイント

- **routers/auth/ と routers/blog/**: いずれもパッケージ化されている。auth は `endpoints` / `github_auth` / `oauth_flow` / `token_manager`、blog は `accounts` / `score` / `sync` に責務分割
- **services/tasks/**: Cloud Tasks（本番）と BackgroundTasks（ローカル）を共通の `execute_task` でディスパッチ。状態遷移（`processing` / `completed` / `dead_letter` / `retrying`）は worker が担う。現在登録されているタスクは `GITHUB_LINK` の 1 種類のみだが、`AsyncTaskCacheService` / `TaskHandler` は新規タスク追加の拡張ポイントとして汎用化してある（インライン化しない）
- **services/intelligence/**: GitHub 連携 → スキル集計パイプライン。`github_link_service` → `pipeline` → `github_collector` → `skill_extractor` が live 経路。LLM は使わず決定論的（ルールベース）に処理する（LLM プロバイダ抽象化は ADR-0008 で撤去済み）
