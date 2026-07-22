---
paths:
  - backend/app/services/agent/**
  - backend/app/prompts/agent_*.md
  - backend/app/schemas/agent.py
  - backend/tests/test_agent.py
  - backend/tests/test_agent_context_builder.py
---

# DevForge Agent 設計ルール（ADR-0010）

詳細な設計判断・経緯は `docs/adr/0010-devforge-agent.md` が正本。
本ファイルは実装時に即参照できる要点をまとめたもの。

## ファイル構成

```
backend/
├── app/
│   ├── prompts/
│   │   ├── agent_base.md          # 共通ルール（全スコープに適用）
│   │   ├── agent_career_summary.md
│   │   ├── agent_self_pr.md
│   │   ├── agent_project.md
│   │   └── agent_experience.md    # Phase 2 追加
│   ├── schemas/
│   │   └── agent.py               # リクエスト/レスポンス Pydantic スキーマ
│   └── services/agent/
│       ├── chat_service.py        # コンテキスト組み立て → LLM → 検証（DB に触れない）
│       ├── context_builder.py     # Phase 2: GitHub 参照コンテキスト取得（DB 読み取り専用）
│       ├── output_schema.py       # tool use スキーマ（機械制約の正本）
│       ├── llm/
│       │   ├── base.py            # LLMClient 抽象・LLMError
│       │   ├── anthropic_client.py # Claude Haiku（本番 / Vertex AI(ADC)）
│       │   ├── ollama_client.py   # ローカル開発（LLM_LOCAL_OLLAMA）
│       │   └── factory.py         # get_llm_client(provider) で分岐（ADR-0023: Anthropic + Ollama の 2 択）
│       └── resume_draft/          # 経歴書ドラフト生成（ADR-0018・0020。下記「resume_draft」節）
│           ├── context.py         # DB 読み取り専用（連携キャッシュ + スキル証跡 → DraftSource）
│           ├── mapper.py          # ルールベース純関数（骨格 payload 構築）
│           ├── output_schema.py   # ドラフト用構造化出力スキーマ（機械制約の正本）
│           ├── draft_service.py   # LLM 1 コール → パース(リトライ1回) → 骨格へマージ（DB 非依存）
│           └── run_task.py        # 非同期タスク本体（ADR-0020: LLM→PDF検証→課金→結果保存。DB 書き込みはここ）
└── tests/
    ├── test_agent.py
    ├── test_agent_context_builder.py  # Phase 2: context_builder の単体テスト
    ├── test_resume_draft_mapper.py    # ADR-0018: ルールベースマッピングの単体テスト
    ├── test_resume_draft_service.py   # ADR-0018: draft_service（LLM モック）
    ├── test_resume_draft_api.py       # ADR-0020: enqueue/status/download の統合テスト
    └── test_worker/test_resume_draft.py  # ADR-0020: run_resume_draft_task（課金順序の不変条件）
```

## resume_draft（経歴書ドラフト生成 / ADR-0018・0020）

GitHub 連携データから経歴書ドラフト payload を組み立てて PDF を生成する機能。**ADR-0020 で
非同期タスク化**した（連携とは別の「ドラフト生成」ボタンで明示実行）。チャットとは別系統だが、
**本ファイルの不変条件（制約の責務分離・リトライ 1 回・エラー契約・LLMError/usage の課金漏れ防止）を
全て継承する**。

- **構造はルールベース、自然文だけ LLM**: repo→プロジェクト骨格・技術スタック・期間は
  `mapper.py`（純関数）が決定論で写す。LLM が生成するのは career_summary / self_pr /
  各プロジェクト description のみ。
- **出力スキーマは動的**: `repo_full_name` を選定リポジトリの enum で縛る（捏造リポの構造排除）。
  チャットの「プロンプトは静的・スキーマも静的」と異なりリクエストごとに構築するが、
  プロンプト md（`agent_resume_draft.md`）自体は静的を維持する（動的情報は user メッセージへ）。
- **非同期タスク + 最小永続化（ADR-0020）**: `TaskType.RESUME_DRAFT` の独立タスク。生成 payload
  だけを連携ドメインの `resume_draft_cache`（1 ユーザー 1 件・最新上書き）に保存し、
  `GET /api/agent/resume-draft/pdf` で再レンダリングする。**`resumes` テーブルへは書かない**
  （確定した Resume と混同させない）。DB 書き込み（課金・結果保存・状態遷移）は `run_task.py` と
  repository に閉じ込め、`draft_service.py` / `mapper.py` / `context.py`（SELECT のみ）の DB 非依存は維持。
- **課金はタスク側（ADR-0020）**: 残高の事前チェック（402）だけ enqueue で行い、実課金は
  `run_task.py` が確定する。**PDF レンダリング成功後にのみ課金**（失敗＝課金なし）、LLM/パース失敗時は
  消費済みトークンを必ず課金、課金記録の失敗は `NonRetryableError` で dead_letter 化（LLM 再実行=再課金を防ぐ）。
- **二重課金を防ぐ原子性・冪等性（ADR-0020）**: 本課金と結果保存（`completed` + `result`）は
  **同一セッションの単一トランザクション**で確定する（`record_chat_usage` の commit が staged な
  cache 変更も一括 flush する）。「課金済みだが結果未保存」の窓を作らないことで、その状態からの
  リトライ・再配信による再課金を構造的に防ぐ。加えてフェーズA に**冪等ガード**を置き、既に
  `completed` かつ `result` があるタスク再配信（原子 commit 後・ack 前のクラッシュ）は再実行しない。
  手動再実行は router が status を `pending` へ戻すためガードに掛からず、意図どおり再生成する。
- **degrade 方針**: 個別プロジェクトの説明文が欠落・上限超過した場合のみ repo description の
  定型文へフォールバック（切り詰めはしない）。career_summary / self_pr の欠落はパース失敗扱い。

## プロバイダ抽象（ADR-0023 で Haiku 一本化）

ADR-0013 のマルチプロバイダ（Anthropic / Gemini / OpenAI）は **ADR-0023 で撤去**し、
本番は Claude Haiku 固定・ローカル開発は Ollama の 2 択に縮退した。

- **本番プロバイダは Anthropic のみ**。`model_catalog` は `haiku` の 1 エントリ、
  `schemas/agent.py:AgentModelAlias` は `Literal["haiku"]`。モデル選択機構は撤去済み。
- **プロバイダ切替は `factory.get_llm_client(provider)` の 1 箇所**に集約する（この原則は維持。
  切替先が Anthropic + Ollama の 2 択に減っただけ）。`LLM_LOCAL_OLLAMA=1` の時だけ provider を
  無視してローカル Ollama に通す（dev 無料パス / ADR-0010）。
- **Anthropic は Vertex AI(ADC) 経由を維持**（ADR-0015 の PII ガバナンスを単一プロバイダでも継続 /
  ADR-0023）。`anthropic[vertex]` / `VERTEX_ANTHROPIC_LOCATION` / `GCP_PROJECT_ID` は残す。
  `ANTHROPIC_API_KEY` 直キー方式には戻さない（データ所在地を失うため）。
- **構造化出力**: Anthropic = tool use（`build_tool_definition`）で `oneOf`/`const`/`maxLength` を
  そのまま解釈できるため元スキーマを使う。Ollama（`format` / llama.cpp GBNF）は数値制約で
  文法変換が壊れるため `to_portable_schema` で `field` を enum 化・上限除去した移植スキーマを渡す。
  上限の実強制は従来どおり `_parse_response` が担う（二重防衛）。
- モデル・プロバイダを再導入する場合は ADR-0023 を `Superseded` にした上で新規 ADR を起票し、
  ADR-0013 の provider 抽象を git 履歴から再評価する（`model_catalog` と `AgentModelAlias` を
  両方更新する drift チェックの前提も復活させる）。

## 制約の責務分離（最重要）

制約を追加・修正する前に、置き場所を必ず以下の基準で判断する。

| 制約の種類 | 例 | 置き場所 |
|---|---|---|
| 機械検証可能 | 許可フィールド名、文字数上限、JSON 構造、配列件数上限 | `output_schema.py`（スキーマ） + `_parse_response`（二重防衛） |
| 機械検証不能 | 文体、構成、PAR 形式、捏造禁止、思考ステップ、曖昧入力への応答方針 | `agent_base.md` / `agent_{scope}.md`（プロンプト） |

**判断基準: コードでテストが書ける制約はプロンプトに書かない。**

### やってはいけないこと

- `agent_*.md` に「JSON のみ出力」「許可フィールドは〇〇」「文字数は〇〇字以内」を書く  
  → スキーマで保証済みのため書くと二重管理になる
- `output_schema.py` の `SCOPE_FIELDS` と異なる上限を `agent.py` の Pydantic フィールドに設定する  
  → `test_scope_limits_match_resume_schema` が drift を検出するが、そもそも揃えること
- プロンプトへの制約追記で問題を解決しようとする  
  → 機械検証可能なものはスキーマへ寄せる。精度問題はまずプロンプト（品質基準・few-shot）で対処する
  （ADR-0023 で Haiku 固定・上位モデルへの昇格パスは撤去済み。再導入は新規 ADR 起票が前提）

## スコープと許可フィールド（正本: `output_schema.py`）

| スコープ | 許可フィールド | 文字数上限 |
|---|---|---|
| `career_summary` | `career_summary` | 2000 |
| `self_pr` | `self_pr` | 2000 |
| `project` | `description` | 4500 |
| `project` | `role` | 200 |
| `experience` | `business_description` | 200 |
| `experience` | `description` | 4500 |

上限値を変更する場合は `output_schema.py` の `SCOPE_FIELDS` を編集する。
`schemas/resume.py` の max_length と一致させること（`test_scope_limits_match_resume_schema` で検証済み）。

## プロンプト編集ルール

### `agent_base.md`（共通ルール）に書くもの

- 全スコープに共通する品質ルール（捏造禁止・プレースホルダ禁止）
- 曖昧入力への応答方針（operations 空 + suggestions 生成）
- ユーザー指示の優先順位
- スキーマ制約との関係を説明する一文（「出力の構造・許可フィールド・文字数上限はスキーマで定義されているため、ここでは内容の品質に集中すること」）

### `agent_{scope}.md`（スコープ固有）に書くもの

- 推奨文字数（「品質基準としての目安」であり上限とは別物であることを明示）
- 構成・文体の品質基準（PAR 形式 / 見出し構成 / Markdown ルール）
- 思考ステップ
- few-shot の出力例（内容は流用しない旨を必ず注記する）

### プロンプトは静的に保つ

プレースホルダ（`{allowed_fields}` 等）を使って動的に埋め込まない。
スコープ固有の制約はスキーマで持つ設計なので、プロンプトはモジュールロード時に完全静的にしてプロバイダのキャッシュを効かせる。

## 新規スコープを追加する手順

1. `output_schema.py` の `SCOPE_FIELDS` にスコープ名とフィールド/上限を追加
2. `agent_{scope}.md` を `backend/app/prompts/` に作成（品質基準・思考ステップ・few-shot）
3. `chat_service._SCOPE_DEFAULT_FIELD` に正規化先を追加
4. `chat_service._build_context` に該当スコープの分岐を追加
5. `schemas/agent.py` の `AgentScope` Literal に追加
6. `test_agent.py` に `test_chat_system_prompt_is_scope_specific` のパラメータを追加
7. `test_scope_limits_match_resume_schema` に上限一致の assert を追加
8. スコープに `target` が必要な場合: `schemas/agent.py` に Target クラスを追加し `validate_target` を拡張する。`validate_target` は project 先行 union を維持すること（既存契約の後退を防ぐ）

## 検証の多段構造（変えてはいけない順序）

```
1. tool use スキーマ（API レベルで構造・必須キーをモデルに提示）
2. JSON パース + AgentChatResponse の Pydantic 検証  → 失敗: AGENT_PARSE_ERROR（リトライ 1 回）
3. _parse_response: 許可外フィールドをスコープ既定フィールドへ正規化
4. _parse_response: 文字数超過の operation を破棄（切り詰めない。ADR-0010 参照）
5. _parse_response: operations がある応答の suggestions を破棄（同時提示しない契約）
```

超過 operation を切り詰めて返すことは**禁止**（途中で切れた経歴書は品質として不可）。

## エラー契約（変えてはいけない）

| 事象 | HTTP | ErrorCode |
|---|---|---|
| project / experience スコープで target 未指定 | 422 | `VALIDATION_ERROR` |
| target インデックスが範囲外 | 422 | `VALIDATION_ERROR` |
| LLM 呼び出し失敗 | 502 | `AGENT_LLM_ERROR` |
| LLM 応答のパース / スキーマ違反（リトライ後も失敗） | 502 | `AGENT_PARSE_ERROR` |
| レート制限超過 | 429 | — |

リトライは **1 回のみ**。違反内容をフィードバックして再生成させる。3 回目は呼ばない。

## DB を更新しない原則

`POST /agent/chat` のレスポンス（operations）はフロントの state にのみ適用する。
ユーザーが「適用」した時点で既存の保存 API（`PUT /resumes` 系）を呼ぶ設計。
Agent エンドポイント自体は DB を書き換えない。この原則を崩してはいけない。

`chat_service.py` は DB に触れない。DB 読み取りは `routers/agent.py` → `context_builder.py` 経由のみとする。

## GitHub 参照コンテキスト（Phase 2）

`career_summary` / `self_pr` スコープのみに GitHub 分析サマリーを付与する。`project` / `experience` には付与しない。

**付与スコープの理由**: career_summary/self_pr はキャリア全体像を表す文章であり、GitHub の言語傾向は LLM が根拠として参照できる。project/experience は特定案件・企業の記述改善用途であり GitHub 情報は文脈として不適切（捏造リスク・トークン浪費）。

**フロー**: `router → build_reference_context(db, user_id, scope) → run_agent_chat(request, reference)`

**degrade 方針**: GitHub 参照データの取得失敗は `None` に degrade しチャット本体を落とさない。`build_reference_context` と各ヘルパーが独立に `try/except Exception` + `logger.warning(exc_info=True)` でラップする。例外を握りつぶさずログを残すこと。

**SELECT のみ**: `context_builder.py` は `commit` / `flush` / `add` を書かない。

## 会話履歴（history）の仕様

- フロントのみで保持（DB 永続化なし。サーバーはセッションを持たない）
- 上限: 3 往復（6 エントリ）。`AgentChatRequest.history max_length=6` と `useAgentChat.ts HISTORY_LIMIT` を同期させる
- assistant エントリは `message` だけでなく **operations を含む応答 JSON 原文**を格納する（few-shot として機能する）
- レジュメコンテキストは最新ターンの user prompt にのみ載せる（履歴側には載せない）

## suggestions の仕様

`AgentChatResponse.suggestions: list[str]` — 曖昧入力で operations を返せないときに LLM が生成する「次の依頼文候補」。

- 上限: 4 件・各 200 字（`output_schema.MAX_SUGGESTIONS` / `MAX_SUGGESTION_LENGTH`）
- operations がある応答で suggestions が返ってきた場合は破棄する（`_parse_response` が担う）
- 空文字・超過候補も破棄する
- フロントはボタンとして表示し、押下テキストをそのまま次の `prompt` として再送信する

## テストの書き方

- LLM はモック（`_FakeLLM`）。DB はモックしない（実 SQLite セッション）
- `output_schema` の単体テスト: スコープ → oneOf 分岐、上限、必須キー、tool 定義のラップ
- drift 防止テスト: `SCOPE_FIELDS` と `schemas/resume.py` の max_length 一致を検証（`test_scope_limits_match_resume_schema`）
- リトライ契約のテスト: `_SequentialFakeLLM` で「失敗→成功」「失敗→失敗」の両パスを検証
- 上限超過の operation が破棄されること、許可外フィールドが正規化されること、suggestions の件数・文字数バリデーションを必ず検証する
- `context_builder` のテストは `test_agent_context_builder.py` に分離する。DB モック禁止（実 SQLite セッション）
