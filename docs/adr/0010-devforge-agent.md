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

`career_summary` / `self_pr` は単一文字列フィールドだが、`project` は配列の深いネスト下にあり「どの experience のどの client のどの project か」をパスで特定する必要がある。差分 operations はこのパス指定を含む設計とする。

## 決定内容

### アーキテクチャ概要

```
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

| スコープ | 対象 | operations 適用先 |
|---|---|---|
| `project` | 選択中の案件（experience/client/project） | 該当 project の `description` ほか（`role` / `technology_stacks` / `phases`） |
| `career_summary` | 職務要約 | `ResumeBase.career_summary` |
| `self_pr` | 自己 PR | `ResumeBase.self_pr` |

スコープ未選択での汎用モードは Phase 1 では提供しない（Phase 3 で検討）。

### DB を更新しない原則

Agent のレスポンス（差分 operations）はフロントの state にのみ反映する。ユーザーが内容を確認して「適用」を押した時点で初めて**既存の保存 API**（`backend/app/routers/resumes.py` の更新エンドポイント）を呼び出す。Agent エンドポイント自体は DB を書き換えない。これにより「AI の提案を確認せず保存してしまう」事故を防ぎ、既存のバリデーション（`Experience.validate_dates` / 各 `model_validator`）を保存時に再利用できる。

### LLM 失敗の UI 伝達（ADR-0004 積み残しの解消）

ADR-0004 の `generate()` は失敗時に空文字を返す設計で、UI がエラーを検知できなかった。本機能は対話型のため、`POST /agent/chat` では LLM 呼び出しの失敗（タイムアウト / モデル未起動 / API エラー / JSON パース失敗）を**明示的に区別して HTTP エラー（日本語メッセージ）で返す**。エラーメッセージは `backend/app/messages.json` を正本とし、frontend は `AppErrorResponse.message` を表示する（`.claude/rules/frontend/messages.md` 準拠）。空文字フォールバックで握りつぶさない。

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
- system prompt 設計・チューニング
- フロント: チャットウィジェット UI
- フロント: スコープ選択 → operations 適用ロジック（state プレビュー、DB 未更新）

**Phase 2（拡張）**

- experience 単位のスコープ追加
- 会話履歴の保持（マルチターン対応）
- GitHub / ブログ分析との連携強化

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
| `backend/app/services/` | `agent_service.py` 追加（スコープデータ組み立て + LLM 呼び出し + 差分生成）。LLM プロバイダ抽象は ADR-0004 を参考に再構築 |
| `backend/app/schemas/` | Agent リクエスト/レスポンス（差分 operations のパス指定）スキーマ追加 |
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
