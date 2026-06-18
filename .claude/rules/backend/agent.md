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
│       ├── context_builder.py     # Phase 2: GitHub/ブログ参照コンテキスト取得（DB 読み取り専用）
│       ├── output_schema.py       # tool use スキーマ（機械制約の正本）
│       └── llm/
│           ├── base.py            # LLMClient 抽象・LLMError
│           ├── anthropic_client.py
│           ├── google_client.py   # Gemini（ADR-0013）
│           ├── openai_client.py   # GPT（ADR-0013）
│           ├── ollama_client.py
│           └── factory.py         # get_llm_client(provider) で分岐（ADR-0013）
└── tests/
    ├── test_agent.py
    └── test_agent_context_builder.py  # Phase 2: context_builder の単体テスト
```

## プロバイダ抽象（ADR-0013）

- プロバイダ選択は **モデルエイリアスの属性**（`model_catalog.ModelSpec.provider`）に紐づき、
  リクエスト単位で切り替わる。グローバルな `LLM_PROVIDER` は廃止。
- **プロバイダ切替は `factory.get_llm_client(provider)` の 1 箇所**に集約する（この原則は維持）。
  `LLM_LOCAL_OLLAMA=1` の時だけ provider を無視してローカル Ollama に通す（dev 無料パス）。
- **構造化出力は 3 方式とも `output_schema.py` 由来**: Anthropic = tool use（`build_tool_definition`）/
  Gemini = `response_schema` / OpenAI = strict `response_format`。後者 2 つは `oneOf`/`const`/`maxLength`
  を受け付けないため `to_portable_schema` で `field` を enum 化・上限除去した移植スキーマを渡す。
  上限の実強制は従来どおり `_parse_response` が担う（二重防衛）。
- 新プロバイダ・新モデルを足すときは `model_catalog`（provider + 実 ID + レート）と
  `schemas/agent.py:AgentModelAlias` を**両方**更新する（drift チェックが落ちる）。

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
  → 機械検証可能なものはスキーマへ、精度問題はモデル昇格（Haiku → Sonnet / Opus / Fable 等、より高性能なモデル）を先に検討する

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

## GitHub/ブログ参照コンテキスト（Phase 2）

`career_summary` / `self_pr` スコープのみに GitHub・ブログ分析サマリーを付与する。`project` / `experience` には付与しない。

**付与スコープの理由**: career_summary/self_pr はキャリア全体像を表す文章であり、GitHub の言語傾向・ブログの執筆頻度は LLM が根拠として参照できる。project/experience は特定案件・企業の記述改善用途であり GitHub/ブログ情報は文脈として不適切（捏造リスク・トークン浪費）。

**フロー**: `router → build_reference_context(db, user_id, scope) → run_agent_chat(request, reference)`

**degrade 方針**: GitHub・ブログ参照データの取得失敗は `None` に degrade しチャット本体を落とさない。`build_reference_context` と各ヘルパーが独立に `try/except Exception` + `logger.warning(exc_info=True)` でラップする。例外を握りつぶさずログを残すこと。

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
