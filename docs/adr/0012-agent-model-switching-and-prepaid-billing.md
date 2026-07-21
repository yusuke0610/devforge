# ADR-0012: Agent モデル切り替えとプリペイドクレジット課金

## ステータス

Superseded by ADR-0023

## コンテキスト

DevForge Agent（ADR-0010）の LLM モデルは `claude-haiku-4-5` をハードコードしている。
精度が欲しい場面で上位モデル（Sonnet）を使いたいが、上位モデルは API 原価が高く
（Haiku: $1/$5、Sonnet: $3/$15 per 1M トークン入力/出力）、無制限に開放すると
運用コストが青天井になる。そこで「Haiku は無料・使い放題、Sonnet は有料」とする
モデル切り替え + 課金機能を導入する。

制約:

- Agent チャットの既存契約（`AgentChatResponse` の構造、DB 非更新原則、エラー契約）は
  崩さない（ADR-0010 / `.claude/rules/backend/agent.md`）
- Cloud Run 単一インスタンス（ADR-0005）+ Turso (libSQL)。分散ロックは不要
- 決済機能の運用は初経験のため、未払い・請求トラブルのリスクを最小化したい

## 決定内容

### 1. モデル切り替えは「エイリアス方式」

- クライアントは `AgentChatRequest.model: Literal["haiku", "sonnet"]`（デフォルト `"haiku"`）で
  モデルを指定する。実モデル ID（`claude-haiku-4-5` 等）はサーバー側の
  `services/agent/model_catalog.py`（SSoT）でマップする
- 任意のモデル文字列をクライアントから受け付けない（コスト爆発・未検証モデルの注入を防ぐ）
- `LLMClient.generate()` の契約を変更し、応答テキストに加えて実トークン使用量
  （`input_tokens` / `output_tokens`）を返す（従来は `response.usage` を捨てていた）

### 2. 課金はプリペイドクレジット方式

- ユーザーは事前にクレジットを購入し、Sonnet 利用時に実トークン量に応じて消費する
- **1 クレジット = $0.0001**（USD ペッグ）。消費レートは API 原価 × **マージン係数 1.5**
  （為替・キャッシュ未ヒット・運用コストのバッファ）
- 課金フロー（1 リクエスト）:
  1. 事前チェック: 残高 > 0（不足なら 402 `INSUFFICIENT_CREDITS`）
  2. LLM 呼び出し → 実トークン数取得
  3. 事後減算: 原子的 UPDATE で残高から実コストを引き、台帳 + 使用ログを記録
- **負残高を許容する**: 事前チェック通過後の実コストが残高を上回った場合、残高は負になる。
  1 リクエストの最大コストは `max_tokens=4096` で有界（〜1,200 クレジット ≈ $0.12）であり、
  予約（reserve-then-settle）方式の複雑さに見合わないと判断した
- **消費記録の失敗は 500 エラーにする**: LLM 応答が得られても課金記録に失敗した場合は
  応答を返さない（課金漏れを黙って通すより、ユーザーに再試行させる方を選ぶ）
- Haiku（無料モデル）は残高チェック・減算なし。使用ログのみ記録する（コスト分析用）

### 3. データモデルは「台帳 + キャッシュ残高」

- `credit_transactions`（台帳・追記専用）: 全ての付与/消費を符号付き `amount` と
  `balance_after` で記録する。監査とデバッグの正本
- `users.credit_balance`（キャッシュ残高）: 事前チェックと表示用。台帳と同一トランザクション内で
  原子的 UPDATE（`credit_balance = credit_balance - :cost`）により更新する
- `agent_usage_logs`: モデル別の実トークン数・コストを記録（無料モデル含む）

### 4. 決済は Stripe Checkout（Phase 2）

- Stripe Checkout Session（`mode="payment"`）でクレジットパックを販売する。
  カード情報は Stripe ホストの決済ページで入力され、自サーバーは一切扱わない
  （PCI DSS 対応不要）
- **入金確定は Webhook（`checkout.session.completed`）が正**。リダイレクト戻り
  （success_url）はユーザーがブラウザを閉じると発生しないため、付与処理に使わない
- Webhook は `Stripe-Signature` の署名検証必須。冪等性は
  `credit_transactions.stripe_session_id` の UNIQUE 制約で担保する（同一イベント再送でも
  二重付与しない）
- パック定義（価格・クレジット数）はコード（`services/billing/pricing.py`）を SSoT とし、
  Checkout には `price_data` で動的に渡す（Stripe ダッシュボードの Price オブジェクトに
  依存しない）

### 5. リリースは 2 フェーズ

- **Phase 1**: モデル切り替え + 使用量記録 + クレジット基盤（残高は ADMIN_TOKEN 認証の
  付与エンドポイントでテスト）
- **Phase 2**: Stripe Checkout 購入フロー + Webhook 入金処理 + 課金ページ

## 代替案

- **月額サブスクリプション（Stripe Billing）**: UX はシンプルだが、更新・解約・支払い失敗
  リトライ（dunning）の運用が必要で初導入には重い。使い放題は原価リスクも大きい
- **従量後払い（Stripe Metered Billing）**: 最も柔軟だが未払いリスクと使用量レポートの
  正確性担保が必要で、実装・運用難度が最も高い。プリペイドは「残高 + 1 リクエスト分の
  有界な負残高（max_tokens=4096 ≈ 1,200 クレジット）」までしか使われないことが構造的に
  保証される（負残高許容は上記「負残高を許容する」と同方針）
- **予約方式（reserve-then-settle）**: 事前に最大コストを引き当てて事後精算する方式。
  二重引当の解放漏れ等の障害モードが増えるため、負残高許容（有界損失）を選んだ
- **残高をテーブル分離（balances テーブル）**: 1 ユーザー 1 行のため `users` カラムで十分

## トレードオフ・既知のリスク

- 負残高: 最大 1 リクエスト分（≈$0.12）の取りはぐれを許容する
- USD ペッグのクレジットを円建てパックで販売するため、為替変動はパック価格定数の
  調整で吸収する（自動連動しない）
- 返金・チャージバックはスコープ外（Stripe ダッシュボードで手動対応 + 管理者付与で
  残高調整）
- 消費記録失敗を 500 にする方針は「LLM 原価は発生したのに応答を捨てる」ケースを生むが、
  頻度は低く（DB 障害時のみ）、課金漏れの常態化より安全側
- Ollama（ローカル開発）は無料扱い・トークン数 0 で記録される。モデルエイリアスは
  anthropic プロバイダのときのみ実質的な意味を持つ

## 将来の移行条件

- Opus 等の第 3 のモデル追加: `model_catalog.py` への 1 エントリ追加 + スキーマの
  Literal 拡張で対応できる設計とする
- 利用が増え同時実行が問題になったら（マルチインスタンス化）、残高更新を
  楽観ロックまたは台帳集計方式へ移行する
- 法人利用等でポストペイドが必要になったら Stripe Metered Billing を再検討する

## 関連リンク

- ADR-0005: Cloud Run Single Instance（単一インスタンス前提の原子的 UPDATE）
- ADR-0010: DevForge Agent（チャット契約・DB 非更新原則）
- `.claude/rules/backend/agent.md`（Agent 実装の不変条件）
- Stripe Checkout: https://docs.stripe.com/payments/checkout
- Stripe Webhook 署名検証: https://docs.stripe.com/webhooks#verify-official-libraries

---

2026-07-22: 機能整理（#517）でプリペイド課金・マルチプロバイダを撤去し Haiku 無料一本化 + レート制限へ縮退したため、[ADR-0023](0023-remove-billing-multiprovider.md) で Superseded とした。
