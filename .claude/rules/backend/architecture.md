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
│   ├── blog.py
│   ├── career_analysis.py
│   ├── download_utils.py
│   ├── health.py
│   ├── github_link.py
│   ├── internal.py      # Cloud Tasks → backend 内部 API
│   ├── master_data.py
│   ├── notifications.py
│   └── resumes.py
├── models/              # SQLAlchemy 2.0 宣言的マッピング
│   ├── user.py / blog.py / cache.py / career_analysis.py
│   ├── master_data.py / notification.py / resume.py
├── schemas/             # Pydantic リクエスト/レスポンススキーマ
│   ├── auth.py / blog.py / career_analysis.py / github_link.py
│   ├── master_data.py / resume.py / shared.py
├── repositories/        # データアクセス層
│   ├── base.py / user.py / blog.py / career_analysis.py
│   ├── master_data.py / notification.py / resume.py
├── services/
│   ├── blog/                    # ブログ収集・技術記事判定・スコア算出
│   │   ├── account_service.py
│   │   ├── collector.py
│   │   ├── scorer.py
│   │   ├── sync_service.py
│   │   └── tech_keywords.json
│   ├── career_analysis/         # キャリア分析（プロンプト組み立て・テックスタックマージ）
│   │   ├── builder.py
│   │   ├── prompt_builder.py
│   │   └── tech_stack_merger.py
│   ├── intelligence/            # GitHub 連携パイプラインと LLM 連携
│   │   ├── pipeline.py
│   │   ├── github_collector.py
│   │   ├── github_link_service.py
│   │   ├── github/              # GitHub API クライアント・リポジトリ解析
│   │   │   ├── api_client.py
│   │   │   └── repo_analyzer.py
│   │   ├── llm_summarizer.py
│   │   ├── llm_advice_service.py
│   │   ├── response_mapper.py
│   │   ├── position_scorer.py
│   │   ├── position_weights.json
│   │   ├── skill_extractor.py
│   │   ├── skill_taxonomy/      # スキル分類（言語・トピック・所有権マップ）
│   │   └── llm/                 # LLM クライアント実装
│   │       ├── base.py
│   │       ├── factory.py
│   │       ├── ollama_client.py
│   │       └── vertex_client.py
│   ├── llm/                     # LLM 入出力サニタイザ等（intelligence/llm とは別）
│   │   └── sanitizer.py
│   ├── tasks/                   # 非同期タスク基盤（Cloud Tasks / ローカル）
│   │   ├── base.py              # TaskType 定義
│   │   ├── exceptions.py        # RetryableError / NonRetryableError
│   │   ├── worker.py            # execute_task（状態遷移・通知）
│   │   ├── dispatch_service.py
│   │   ├── factory.py
│   │   ├── cloud_tasks.py       # Cloud Tasks エンキュー
│   │   ├── local.py             # BackgroundTasks 直接実行
│   │   └── handlers/            # タスク種別ごとのハンドラ
│   │       ├── base.py          # TaskHandler 抽象基底クラス
│   │       ├── blog_summarize.py
│   │       ├── career_analysis.py
│   │       └── github_link.py
│   ├── markdown/                # Markdown テンプレート生成
│   ├── pdf/                     # WeasyPrint による PDF 生成
│   ├── progress_service.py      # 進捗状態管理
│   └── shared/                  # ドメイン横断の service util
│       └── sort_utils.py
├── prompts/             # LLM プロンプトテンプレート
├── fonts/               # PDF 生成用フォント
└── utils/
    └── prompt_loader.py # プロンプトファイルローダ
```

## 主要モジュールのポイント

- **routers/auth/**: パッケージ化されており、`endpoints` / `github_auth` / `oauth_flow` / `token_manager` に責務分割
- **services/tasks/**: Cloud Tasks（本番）と BackgroundTasks（ローカル）を共通の `execute_task` でディスパッチ。状態遷移（`processing` / `completed` / `dead_letter` / `retrying`）は worker が担う
- **services/intelligence/**: GitHub 連携 → スキル集計パイプライン。Ollama / Vertex AI を `LLMClient` 抽象で切替
- **services/llm/ と services/intelligence/llm/**: 別物。前者は入出力サニタイザ等の横断 util、後者は LLM プロバイダクライアントの実装
