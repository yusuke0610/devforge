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
│   ├── download_utils.py
│   ├── health.py
│   ├── github_link.py
│   ├── internal.py      # Cloud Tasks → backend 内部 API
│   ├── master_data.py
│   ├── notifications.py
│   └── resumes.py
├── models/              # SQLAlchemy 2.0 宣言的マッピング
│   ├── user.py / cache.py
│   ├── master_data.py / notification.py / resume.py
├── schemas/             # Pydantic リクエスト/レスポンススキーマ
│   ├── auth.py / github_link.py
│   ├── master_data.py / resume.py / shared.py
├── repositories/        # データアクセス層
│   ├── base.py / user.py
│   ├── master_data.py / notification.py / resume.py
├── services/
│   ├── agent/                   # DevForge Agent（LLM チャット / ADR-0010・0012・0013）
│   │   ├── chat_service.py      # コンテキスト組み立て → LLM → operations 検証
│   │   ├── context_builder.py   # GitHub 参照コンテキスト取得（DB 読み取り専用）
│   │   ├── model_catalog.py     # エイリアス→provider/実モデル ID/課金レート（SSoT / ADR-0012・0013）
│   │   ├── output_schema.py     # 構造化出力スキーマ（機械制約の正本）
│   │   ├── llm/                 # LLM プロバイダ抽象（失敗は raise / ADR-0013）
│   │   │   ├── base.py          # LLMClient 抽象・LLMError・共通ヘルパ
│   │   │   ├── factory.py       # get_llm_client(provider) で分岐
│   │   │   ├── anthropic_client.py / openai_client.py / google_client.py
│   │   │   └── ollama_client.py # ローカル開発用（LLM_LOCAL_OLLAMA）
│   │   └── resume_draft/        # GitHub 連携データ → 経歴書ドラフト生成（ADR-0018）
│   │       ├── context.py       # DB 読み取り専用（連携キャッシュ + スキル証跡 → DraftSource）
│   │       ├── mapper.py        # ルールベース純関数（骨格 payload 構築）
│   │       ├── output_schema.py # ドラフト用 LLM 構造化出力スキーマ
│   │       └── draft_service.py # LLM 1 コール → パース → 骨格へ自然文マージ
│   ├── intelligence/            # GitHub 連携パイプライン（決定論的・ルールベース）
│   │   ├── pipeline.py
│   │   ├── github_collector.py
│   │   ├── github_link_service.py
│   │   ├── github/              # GitHub API クライアント・リポジトリ解析
│   │   │   ├── api_client.py
│   │   │   └── repo_analyzer.py
│   │   ├── response_mapper.py
│   │   └── skills/               # スキル推論基盤（ADR-0016 / 3層モデル）
│   │       ├── aggregator.py    # discover+declare+verify 合流 → DetectedSkill
│   │       ├── linguist.py      # 言語正規化（Linguist languages.yml）
│   │       ├── manifests/       # エコシステム別 manifest パーサ（declare / plugin 型）
│   │       └── imports/         # エコシステム別 import スキャナ（verify / plugin 型）
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

- **routers/auth/**: パッケージ化されている。auth は `endpoints` / `github_auth` / `oauth_flow` / `token_manager` に責務分割
- **services/tasks/**: Cloud Tasks（本番）と BackgroundTasks（ローカル）を共通の `execute_task` でディスパッチ。状態遷移（`processing` / `completed` / `dead_letter` / `retrying`）は worker が担う。現在登録されているタスクは `GITHUB_LINK` の 1 種類のみだが、`AsyncTaskCacheService` / `TaskHandler` は新規タスク追加の拡張ポイントとして汎用化してある（インライン化しない）
  - **タスクハンドラの「黙って return」は禁止**: 失敗パスでは `NonRetryableError` / `RetryableError` を `raise` し、`dead_letter` / `retrying` 遷移と通知発行を worker に任せる。早期 return すると呼び出し側に completed として観測されてしまう
- **services/intelligence/**: GitHub 連携 → スキル推論パイプライン。`github_link_service` → `github_collector`（収集）→ `skills/aggregate_skills`（ADR-0016 の 3 層スキル検出）→ `pipeline.aggregate_intelligence`（dashboard 表示用サマリ）が live 経路。旧 `skill_extractor` / `skill_taxonomy`（自前辞書）は ADR-0016 基盤へ移行完了済みで撤去。LLM は使わず決定論的（ルールベース）に処理する（intelligence モジュールは LLM を使わない。LLM は services/agent/ のみ / ADR-0010）
