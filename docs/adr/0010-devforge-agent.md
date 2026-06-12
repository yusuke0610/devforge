# ADR-0010: DevForge Agent 機能の導入

## ステータス

Accepted

## コンテキスト

DevForge は現在、手入力データをもとに職務経歴書（`Resume`）を生成する「経歴書ビルダー」に留まっている。本来の価値である「GitHub・ブログ分析データを活用したキャリア戦略支援」を実現するために、蓄積データをコンテキストとして持つ LLM Agent 機能を追加する。

この判断は ADR-0008 で「LLM をサービス内で使う可能性は低い」としてルールベース設計に一本化し LLM プロバイダ抽象化を撤去した方針を覆すものである。ADR-0008 の「将来の移行条件」に従い、本 ADR の起票をもって **ADR-0008 を `Superseded by ADR-0010` とする**（再導入時の手続きは ADR-0008 が規定済み）。

ただし今回再導入する LLM の用途は ADR-0004 / ADR-0008 時代の「キャリア分析・PDF からの AI 抽出（バックグラウンド非同期処理・ルールベースパイプラインの一部）」とは異なり、**ユーザー対話型のフォアグラウンド機能（チャット）**である。したがって ADR-0004 で積み残した「LLM 失敗を UI に伝達できない（`generate()` が失敗時に空文字を返す）」という既知のリスクを、本機能では設計段階で解消する（後述）。

### 現行スキーマの前提（実装との照合結果）

`backend/app/schemas/resume.py` を確認した結果、Agent が扱う 3 スコープは現行スキーマ上で次の位置にある。これは「差分 operations のパス指定」設計に影響する。

| スコープ | 現行スキーマ上の位置 | 構造 |
|---|---|---|
| `career_summary` | `ResumeBase.career_summary`（`str`, `max_length=2000`, 必須） | トップレベルのフラットなフィールド |
| `self_pr` | `ResumeBase.self_pr`（`str`, `max_length=2000`, 必須） | トップレベルのフラットなフィールド |
| `project` | `Experience.clients[].projects[].description`（`str`, `max_length=4500`） | `experiences[] > clients[] > projects[]` の深いネスト |

`career_summary` / `self_pr` は単一文字列フィールドだが、`project` は配列の深いネスト下にあり「どの experience のどの client のどの project か」を特定する必要がある。対象 project の位置はリクエストの `target` で確定し、LLM の差分 operations はスコープ内のフィールド名と置換値だけを返す。

## 決定内容

### アーキテクチャ概要

```text
[フロント]
ユーザーがスコープを選択（必須）
↓ プロンプト入力
POST /agent/chat
↓
[FastAPI]
スコープデータ + GitHub/ブログサマリーを組み立て
↓ Claude API (Haiku 4.5)
差分 operations + message を返却
↓
[フロント]
resume state に差分適用（DB 更新なし）
↓ ユーザーが確認して「適用」
既存の保存 API（PUT /resumes 系）を呼び出し
```

### LLM モデル

- **採用**: Claude Haiku 4.5（モデル ID: `claude-haiku-4-5`）
- **料金**: $1.00 / 1M input トークン、$5.00 / 1M output トークン（2026-06 時点の正規料金）
- **理由**: 差分生成に特化した小さい JSON を返させる用途のため、重いモデルは不要。精度不足が判明した場合は Sonnet 4.6（`claude-sonnet-4-6`, $3.00 / $15.00）へ切り替える。
- **ローカル開発**: Ollama（ローカル LLM）を使用し API コストを発生させない。ADR-0004 と同じ「ローカル=ローカル LLM / 本番=ホスト型 API」の dev/prod 分離思想を踏襲する。切り替えはプロバイダ抽象 1 箇所に閉じ込め、呼び出し側コードを変えない。

> 補足: 元の検討メモでは Haiku 4.5 の料金を $0.25 / $1.25 と記載していたが、これは旧 Haiku 3.x 世代の料金であり Haiku 4.5 の実料金ではない。正規料金 $1.00 / $5.00 に補正した。コスト試算（トークン量見積り・月額予測）はこの数値で行うこと。

### スコープ設計（Phase 1）

Agent が対応するスコープは以下の 3 種類。スコープはフロントで**必須選択**とし、選択に応じて対象データ（および対応する operations の適用先パス）が自動セットされる。

| スコープ | 対象 | operations 適用先 | GitHub/ブログ参照 |
|---|---|---|---|
| `project` | 選択中の案件（experience/client/project） | 該当 project の `description` ほか（`role` / `technology_stacks` / `phases`） | なし |
| `career_summary` | 職務要約 | `ResumeBase.career_summary` | あり（Phase 2） |
| `self_pr` | 自己 PR | `ResumeBase.self_pr` | あり（Phase 2） |
| `experience` | 選択中の在籍企業（experience） | 該当 experience の `business_description` / `description`（Phase 2） | なし |

スコープ未選択での汎用モードは Phase 1 では提供しない（Phase 3 で検討）。

### DB を更新しない原則

Agent のレスポンス（差分 operations）はフロントの state にのみ反映する。ユーザーが内容を確認して「適用」を押した時点で初めて**既存の保存 API**（`backend/app/routers/resumes.py` の更新エンドポイント）を呼び出す。Agent エンドポイント自体は DB を書き換えない。これにより「AI の提案を確認せず保存してしまう」事故を防ぎ、既存のバリデーション（`Experience.validate_dates` / 各 `model_validator`）を保存時に再利用できる。

### LLM 失敗の UI 伝達（ADR-0004 積み残しの解消）

ADR-0004 の `generate()` は失敗時に空文字を返す設計で、UI がエラーを検知できなかった。本機能は対話型のため、`POST /agent/chat` では LLM 呼び出しの失敗（タイムアウト / モデル未起動 / API エラー / JSON パース失敗）を**明示的に区別して HTTP エラー（日本語メッセージ）で返す**。エラーメッセージは `backend/app/messages.json` を正本とし、frontend は `AppErrorResponse.message` を表示する（`.claude/rules/frontend/messages.md` 準拠）。空文字フォールバックで握りつぶさない。

### LLM 出力制御と制約の責務分離

Agent の LLM 出力制御は JSON mode ではなく、プロバイダの構造化出力機構を使う。

- 本番 Anthropic: Messages API の tool use を `tool_choice` で強制し、`propose_revision` tool の `input_schema` に従う入力を返させる
- ローカル Ollama: `/api/chat` の `format` に同じ JSON Schema を渡し、ローカル開発でも構造化出力に寄せる

制約は次の基準で責務を分離する。

| 制約の種類 | 例 | 守らせる場所 |
|---|---|---|
| 機械検証可能 | JSON 構造、必須キー、許可フィールド、文字数上限、配列件数上限 | tool use の JSON Schema + `AgentChatResponse` / `AgentOperation` の Pydantic 検証 + `_parse_response` のスコープ検証 |
| 機械検証不能 | 文体、構成、PAR 形式、捏造禁止、情報不足時の確認、思考ステップ | system prompt（`backend/app/prompts/agent_*.md`） |

判断基準は「コードでテストが書ける制約はプロンプトに書かない」。そのため、プロンプトには JSON のみ・コードフェンス禁止・許可フィールド列挙・保存上限の数値制約を書かない。スコープごとの許可フィールドと上限は `backend/app/services/agent/output_schema.py` を正本とし、`career_summary` / `self_pr` / `project` ごとに tool schema を切り替える。

ただし Anthropic tool use と Ollama `format` は `maxLength` を API 側で厳密に強制するとは限らないため、Pydantic と `_parse_response` で二重に検証する。上限超過の operation は切り詰めず破棄する。

### エラー契約

`POST /api/agent/chat` のエラーは以下の契約で返す（実装: `backend/app/routers/agent.py` / `backend/app/services/agent/chat_service.py`）。メッセージ正本は `backend/app/messages.json` の `error.agent`。

| 事象 | HTTP | ErrorCode | messages.json キー |
|---|---|---|---|
| project / experience スコープで target 未指定 | 422 | `VALIDATION_ERROR` | `agent.target_required`（schema validator で発火） |
| target インデックスが範囲外 | 422 | `VALIDATION_ERROR` | `agent.target_not_found` |
| LLM 呼び出し失敗（タイムアウト / API エラー / モデル未起動） | 502 | `AGENT_LLM_ERROR` | `agent.llm_failed` |
| LLM 応答の JSON パース / スキーマ検証失敗 | 502 | `AGENT_PARSE_ERROR` | `agent.parse_failed` |
| レート制限超過（`slowapi` 10/minute） | 429 | — | slowapi 既定 |

LLM 出力の検証は次の多段で行い、バリデーションを通過したもののみフロントに返す:

1. tool use / `format` に渡した JSON Schema で構造・必須キー・許可フィールド・上限をモデルに提示する
2. JSON パース + `AgentChatResponse` の Pydantic 検証（失敗は `AGENT_PARSE_ERROR`）
3. 許可外の `field` 名はスコープの既定フィールドへ正規化する（スコープ選択で編集対象は確定しており、提案を捨てるよりユーザー利益が大きい）
4. **文字数上限を超過した operation は切り詰めず破棄する**（warning ログを残す）。`message` は返るため、ユーザーは依頼を変えて再指示できる

文字数超過時にバックエンドで切り詰めて返す案は**却下**した。文章が途中で切れた経歴書は品質として許容できないためである（「代替案」参照）。

**曖昧入力のフォールバック**: 改善に必要な情報が不足している場合、LLM は事実を捏造せず `operations` を空配列にし、`message` で必要な情報をユーザーに確認する（system prompt の共通ルールで規定）。依頼が曖昧・抽象的なときはこれに加えて、LLM が `suggestions`（次の依頼文候補の文字列配列）を生成して選択肢を提示する（「対話型選択肢（LLM 生成 suggestions）設計」参照）。

### コスト設計

#### system prompt のスコープ分岐

system prompt は共通ルール（`agent_base.md`）＋**選択スコープの md 1 枚のみ**（`agent_{scope}.md`）を結合する。3 スコープ分を全結合すると毎リクエスト約 2,000 トークンの無駄が出ることに加え、無関係なスコープの品質基準（文字数制限等）を小型モデルが取り違える品質問題があるため、スコープ分岐を必須とする。プレースホルダ（`{allowed_fields}` / `{field_limits}`）はスコープごとに静的なためモジュールロード時に埋め込み、system prompt を完全静的化してプロバイダ側のプロンプトキャッシュを効かせる。

#### コンテキスト圧縮（GitHub / ブログ連携時の契約）

Phase 2 で GitHub / ブログ分析を Agent コンテキストに渡す際は、生データではなく**派生サマリーに圧縮**して渡す。

**github_context（~200 トークン以下）**

- `languages` 上位 5 件（バイト数または割合）
- 年ごとの `total_contributions`（`contribution_calendars` から `weeks` を捨てて集計）
- 直近 12 ヶ月の活動日数

`contribution_calendars` の日次グリッド（1 年分で約 4,500〜5,500 トークン）はヒートマップ描画用の構造であり、LLM コンテキストとしては渡さない。

**blog_context（~200 トークン以下）**

- 更新頻度サマリー（`avg_monthly_posts` / `tech_article_count` 等）
- 直近記事のタイトル・タグ

記事本文・全記事リストは渡さない。

### 会話履歴（マルチターン）

当初 Phase 2 予定だったが、推敲の連続性（「さっきの提案のここだけ直して」）が Phase 1 の中核 UX に直結するため **Phase 1 に前倒しして実装済み**。

- 履歴は**フロントのみ**で保持する（DB 永続化なし。サーバーはセッションを持たない）
- ページリロードで履歴はリセットされる。スコープ切り替えでは履歴を保持する（各エントリが送信時のスコープ・target を持ち、適用時に参照する）
- **3 往復（user + assistant で 6 エントリ）**を上限とし、超過分は古いものから切り詰める（`AgentChatRequest.history` の `max_length=6` とフロント `useAgentChat.ts` の `HISTORY_LIMIT` で同期）
- assistant メッセージは `message` だけでなく **`operations`（提案した本文）を含む応答 JSON 原文**を履歴に保持する。推敲の連続性に加え、出力形式の実例として few-shot 的に働き小型モデルのフォーマット逸脱を抑える
- レジュメコンテキストは最新ターンの prompt にのみ載せる（履歴側は依頼文 / 応答 JSON のみで、毎ターンの重複でトークンが膨れるのを防ぐ）

リクエストスキーマ（実装準拠）:

```json
{
  "scope": "self_pr",
  "prompt": "もっと簡潔にして",
  "resume": { "career_summary": "...", "self_pr": "...", "experiences": [] },
  "target": null,
  "history": [
    { "role": "user", "text": "自己PRを改善して" },
    { "role": "assistant", "text": "{\"message\": \"...\", \"operations\": [...]}" }
  ]
}
```

**将来の検討事項（Phase 2 以降）**: 履歴往復数の拡大は operations 込みでトークン量が線形に増えるため、コンテキスト圧縮（上記）とセットで再評価する。

### 対話型選択肢（LLM 生成 suggestions）設計

#### 背景

曖昧な自由入力（「いい感じにして」等）は LLM の出力精度を下げる（特にローカルの小型モデル）。入力は**フリーテキストのみ**とし、依頼が曖昧で意図を特定できないときに **LLM 自身が対話の流れに沿った選択肢（次の依頼文の候補）を生成して提示**する。ユーザーは選択肢をタップするだけで意図を具体化でき、言語化の負担が下がる。

#### レスポンスの `suggestions`

`AgentChatResponse.suggestions: list[str]`。LLM が生成する「次の依頼文」候補で、フロントはボタンとして表示し、押下されたテキストを**そのまま次の `prompt` として再送信**する（専用 API・専用フィールドは増やさない）。

- system prompt（`agent_base.md` の共通ルール）で規定: 依頼が曖昧・抽象的で operations を返せないときは、`message` で確認しつつ `suggestions` に具体的な依頼文の候補を **2〜4 個**入れる（ユーザーがそのまま送れる命令形の日本語）。通常の提案時は空配列
- バックエンド（`chat_service._parse_response`）の検証: 空文字・200 字超の候補は破棄、最大 4 件に切り詰め。**operations がある応答に suggestions が混ざっていた場合は破棄**する（提案と選択肢の同時提示は UI が混乱するため）
- 小型モデルが suggestions を返せない場合は空配列に degrade し、従来どおり `message` のみで対話する（機能破壊にならない）

#### フロントエンド UI

- 入力はフリーテキストのみ（事前定義のアクションボタンは置かない）
- assistant メッセージに `suggestions` が含まれる場合、メッセージ直下に候補ボタンを表示する（`AgentChatWidget` の `SuggestionButtons`）
- ボタン押下で候補テキストを通常のフリーテキスト送信と**同じ経路**（`useAgentChat.send`）で送信する。チャット欄・LLM 履歴にもそのテキストが user 発話として残る

### セキュリティ・横断要件

- **認証ガード**: `POST /agent/chat` は `get_current_user` 依存を付与する（未認証アクセス不可）。
- **Rate Limit**: 外部 API を叩く高コスト endpoint のため `slowapi` でレート制限を付ける（`.claude/rules/backend/auth-security.md`）。
- **環境変数**: `ANTHROPIC_API_KEY` を新規追加する。`backend/app/core/env_keys.py` を正本に定数定義し、env_keys のコメントが規定する 5 箇所同期（env_keys / `infra/modules/cloud_run/main.tf` / `.github/workflows/ci.yml` / `docker-compose.yml` / `docs/api.md`）を行う。backend 内で `os.getenv("ANTHROPIC_API_KEY")` のリテラル参照は禁止。本番では Secret Manager 経由で注入する。
- **入力バリデーション**: リクエスト body は `app/schemas/` の Pydantic モデルで型・制約を検証する（`Any` / `dict` 素通し禁止）。

## 実装フェーズ

**Phase 1（初期リリース）**

- `POST /agent/chat` エンドポイント実装（認証ガード + rate limit）
- スコープ 3 種（`project` / `career_summary` / `self_pr`）対応
- 差分 operations のパス指定スキーマ設計
- tool use 用のスコープ別出力スキーマ設計
- system prompt 設計・チューニング（機械検証不能な品質制約のみ）
- フロント: チャットウィジェット UI
- フロント: スコープ選択 → operations 適用ロジック（state プレビュー、DB 未更新）
- 会話履歴の保持（マルチターン対応。当初 Phase 2 予定から前倒し。「会話履歴（マルチターン）」参照）

Phase 1 追補（対話型選択肢。「対話型選択肢（LLM 生成 suggestions）設計」参照、実装済み）:

- [x] レスポンスに `suggestions: list[str]` 追加（LLM が生成、`_parse_response` で検証）
- [x] system prompt（`agent_base.md`）に曖昧入力時の suggestions 生成ルールを追加
- [x] フロント: suggestions ボタン表示（押下でそのテキストを prompt として再送信）

**Phase 2（拡張）— 実装済み**

- [x] experience 単位のスコープ追加
- [x] GitHub / ブログ分析との連携強化（「コスト設計」のコンテキスト圧縮契約に従う）

#### Phase 2 の設計判断

**resume コンテキストは FE state から取得**

GitHub・ブログ分析データは backend が DB から読み取るが、resume コンテキスト（経歴書の編集対象データ）は FE の state から取得する。理由:

1. **未保存編集の可視性**: LLM が見る context と FE が差分適用する state が一致しなければ、operations の適用先を誤る
2. **差分適用の整合性**: DB に寄せると、ユーザーの未保存編集が LLM に見えずに差分 operations が生成されるため、適用後の state が期待と乖離する
3. **未保存 resume でも動作**: 初めて使うユーザーがまだ保存していない状態でも Agent を利用できる

GitHub・ブログは「参照データ（read-only な分析結果）」として DB から読む。resume は「編集対象（mutable な下書き）」として FE state から読む。この責務分離は変更しない。

**experience スコープの許可フィールドと target 設計**

`experience` スコープは `business_description`（200 字）と `description`（4500 字）の 2 フィールドを許可する。`AgentExperienceContext` に `description` / `is_it_company` を追加し、non-IT 企業（`is_it_company=false`）では `description` が職務本文になることを LLM が分岐判断できるようにする。

target union は `ProjectTarget | ExperienceTarget` とし `ExperienceTarget(extra="forbid")` を追加した。`extra="forbid"` により ProjectTarget の 3 キー payload が ExperienceTarget にマッチしない。Phase 1 の project 契約（3 キー必須）を後退させない。

**GitHub/ブログ参照コンテキストの付与スコープ**

`career_summary` / `self_pr` のみに付与する。`project` / `experience` には付与しない。理由:

- project/experience は特定の案件・企業の記述を改善する用途であり、GitHub/ブログ情報は文脈として不適切（捏造リスク・トークン浪費）
- career_summary/self_pr はキャリア全体像を表す文章であり、GitHub の言語傾向・ブログの執筆頻度・記事タイトルは LLM が根拠として参照できる

**degrade 方針**

GitHub・ブログ参照データの取得失敗（未連携・processing 中・0 件・DB 例外）はいずれも `None` に degrade し、チャット本体を落とさない。`build_reference_context` と各ヘルパーが独立に `try/except Exception` + `logger.warning(exc_info=True)` でラップする。

**圧縮の実装値（ADR コスト設計の具体化）**

| 項目 | 上限 |
|---|---|
| `languages_top5` | 上位 5 言語（バイト数 → 割合 % に変換） |
| `contributions_by_year` | 直近 5 年分（weeks は捨てる） |
| `active_days_last_12_months` | 直近 365 日の count > 0 日数 |
| `recent_articles` | 直近 5 件（タイトル・タグ先頭 5 個・published_at のみ） |

**Phase 3（将来）**

- スコープ未選択でも動く汎用モード
- モデルを Sonnet 4.6 へ切り替え検討

## 代替案

**resume_state 全体を返す（差分 operations ではなく）**
`Resume` のネスト構造（`experiences[] > clients[] > projects[] > {periods, team, technology_stacks, phases}`）が深く、Haiku では JSON 構造を崩すリスクがある。差分 operations に絞ることで精度とコストを両立する。採用しない。

**Node.js PDF 生成マイクロサービス**
2 コンテナ構成になりデプロイ・管理コストが増大するため却下。PDF 生成は既存の Python バックエンド（WeasyPrint）を継続使用する。

**pdfme カスタムテンプレート（今回の優先度外）**
DevForge の本質的価値は「蓄積データ × LLM による経歴書生成」であり、PDF レイアウトのカスタマイズは副次的機能と判断。Agent 機能が完成し GitHub・ブログ分析との連携が充実した段階で改めて検討する。

**事前定義のアクションカタログ（定型ボタン）**
スコープごとの定型改善依頼を `agent_actions.yaml` + `GET /api/agent/actions` + `action_id` で提供する案。一度実装したが却下した。定型ボタンはユーザーの文脈・対話の流れに合わない提案になりやすく、曖昧入力への選択肢は LLM が対話に沿って生成する方が適切。カタログとエンドポイントの保守コストも不要になる。入力はフリーテキストのみとし、選択肢は LLM 生成の `suggestions` で提示する。採用しない。

**文字数超過時のバックエンド切り詰め**
LLM が文字数上限を超える `value` を返した場合に、バックエンドで上限まで切り詰めて返す案。文章が途中で切れた経歴書は品質として許容できないため却下。超過 operation は破棄（warning ログ）し、`message` でユーザーに再指示を促す（「エラー契約」参照）。採用しない。

**JSON mode + プロンプトによる制約記述の継続**
JSON mode を使い、許可フィールド・文字数上限・JSON 構造などを自然言語プロンプトに列挙し続ける案。制約が増えるたびに system prompt が肥大化し、自然言語による制約遵守はモデル任せで保証がないため却下する。機械検証可能な制約は tool use の JSON Schema と Pydantic に寄せる。

**LLM を再導入せずルールベースを維持（ADR-0008 の現状維持）**
対話的なキャリア戦略支援はルールベースでは表現力が不足する。本機能の中核価値が LLM による自由記述生成であるため、ADR-0008 を Superseded として LLM を再導入する。

## トレードオフ・既知のリスク

- **LLM 再導入に伴う運用コスト**: API コスト（従量課金）・プロバイダ抽象・env・依存の再構築が必要。ADR-0008 で撤去した資産を ADR-0004 の設計を参考に再構築する（ただし対話型ゆえ失敗の握りつぶしは行わない）。
- **差分 operations のパス整合**: フロントの resume state とバックエンドが返すパス（特に `project` の深いネスト）がズレると適用に失敗する。パス指定スキーマを BE/FE で同期させる仕組みが要る（OpenAPI 生成物経由が望ましい）。
- **Haiku の構造化出力精度**: 小さい JSON でも構造崩れの可能性は残る。パース失敗時は明示エラーで返し、リトライ/モデル昇格（Sonnet 4.6）の判断材料とする。
- **コスト見積りの前提**: 料金は Haiku 4.5 の正規値（$1.00 / $5.00）で算定する。旧 $0.25 / $1.25 前提の試算は過小評価になるため使わない。

## 将来の移行条件

- **モデル昇格**: 差分生成の精度が Haiku で不足する場合、`claude-sonnet-4-6` へ切り替える。プロバイダ/モデル切り替えは抽象層 1 箇所で完結させる。
- **再びの LLM 撤去**: 将来 LLM 利用を再び停止する場合は、本 ADR を `Superseded` とした上で新規 ADR を起票する（ADR-0008 と同じ手続き）。
- **codegen 系統**: `POST /agent/chat` の追加・スキーマ変更は OpenAPI スペックに反映されるため、`make codegen-types` で `frontend/src/api/generated.ts` を再生成し同一 PR でコミットする（ADR-0007 / `codegen-drift`）。

## 影響範囲

| 対象 | 変更内容 |
|---|---|
| `backend/app/routers/` | `agent.py` 追加（`POST /agent/chat`、認証ガード + rate limit） |
| `backend/app/services/` | `agent/chat_service.py` 追加（スコープデータ組み立て + LLM 呼び出し + 差分生成）。LLM プロバイダ抽象は ADR-0004 を参考に再構築 |
| `backend/app/schemas/` | Agent リクエスト/レスポンス（スコープ内フィールドの差分 operations）スキーマ追加 |
| `backend/app/messages.json` | Agent 関連のエラーメッセージ（LLM 失敗・パース失敗）追加 |
| `backend/app/core/env_keys.py` ほか 4 箇所 | `ANTHROPIC_API_KEY` 追加（5 箇所同期） |
| `frontend/src/` | チャットウィジェットコンポーネント追加 |
| `frontend/src/api/` | `/agent/chat` クライアント追加 |
| `frontend/src/api/generated.ts` | OpenAPI 再生成（`make codegen-types`） |
| ローカル | Ollama セットアップ |

## 関連リンク

- [ADR-0004: LLM プロバイダ抽象化（Ollama/Vertex AI）の設計判断](0004-llm-provider-abstraction.md)
- [ADR-0008: LLM プロバイダ抽象化の撤去とルールベース設計への統一](0008-remove-llm-to-rule-based-design.md)（本 ADR で Superseded）
- [ADR-0007: OpenAPI → TypeScript codegen](0007-openapi-typescript-codegen.md)
