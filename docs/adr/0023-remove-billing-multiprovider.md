# ADR-0023: プリペイド課金・マルチプロバイダの撤去と Haiku 無料一本化

## ステータス

Accepted

## 関連 ADR

- Supersedes: [ADR-0012](0012-agent-model-switching-and-prepaid-billing.md)（モデル切替 + プリペイド課金）、[ADR-0013](0013-multi-provider-llm-selection.md)（マルチプロバイダ選択）、[ADR-0015](0015-vertex-ai-for-gemini-anthropic.md)（Gemini/Anthropic の Vertex AI 経路。**ただし Anthropic を Vertex AI(ADC) で叩く認証判断は本 ADR に引き継ぐ**。撤去するのは Gemini/OpenAI マルチプロバイダ部分のみ）
- 関連: [ADR-0010](0010-devforge-agent.md)（Agent の不変条件・dev/prod 分離思想を継承）、[ADR-0018](0018-github-resume-draft-generation.md) / [ADR-0020](0020-async-resume-draft-generation.md)（ドラフト生成の課金配線を剥がす）、[ADR-0005](0005-cloudrun-single-instance.md)（レート制限の原子的カウントの前提）

## コンテキスト

機能整理（#517）でユーザ目線の障害を棚卸しした結果、**Agent 利用の最大の障害は「2 段落の文章改善のためにカード登録してチャージする」プリペイド課金の壁**だと判断した。

- Agent の実用途は小さな構造化 JSON（operations）の生成であり、ADR-0010 自身が `claude-haiku-4-5` で十分と判断していた。上位モデル（Sonnet）課金は「あると嬉しい」レベルで、壁のコストに見合わない。
- マルチプロバイダ 3 社（ADR-0013: Anthropic / Gemini / OpenAI）+ Vertex 経路（ADR-0015）+ Stripe プリペイド（ADR-0012）は、個人開発規模（ADR-0005）に対して過剰装備。保守対象が広い（billing 348 行 + Stripe webhook + 3 プロバイダクライアント + Vertex/ADC + 複数 API キー env + 課金/使用ログテーブル）。
- Haiku は安価（$1/$5 per 1M tokens）で、無料開放しても運営コストは限定的。ただし**クレジット残高が事実上の abuse 防止だった**ため、それが消える分の蓋（レート制限）が要る。

## 決定内容

**本番の Agent を Claude Haiku 無料一本化 + ユーザ単位レート制限に縮退する。** プリペイド課金・マルチプロバイダ抽象・モデル選択を撤去し、保守面を最小化しつつ「課金の壁」を除いて体験を上げる。

### 縮退後の構成

- **本番 LLM**: Claude Haiku 固定（モデル選択・エイリアス機構を撤去）
- **ローカル開発**: Ollama（`LLM_LOCAL_OLLAMA`。ADR-0010 の dev/prod 無料パスを維持）
- **abuse 防止**: ユーザ単位の日次レート制限（クレジット残高チェックの代替）
- **課金**: 撤去（Stripe / プリペイドクレジット / 使用ログ課金を全廃）

### 撤去順序（後続 3 PR の指針。順序が重要）

1. **#521 レート制限導入（先行必須）**: 課金撤去で消える abuse 防止の代替を**先に**入れる。`/agent/chat`・`/agent/resume-draft/pdf` にユーザ単位日次上限。決定論ロジックとして TDD（mutmut 対象）。上限は env 化。
2. **#522 課金撤去**: `routers/billing.py`・`services/billing/`（`credit_service` / `pricing` / `stripe_service`、348 行）・Stripe webhook・課金/使用ログテーブルの drop マイグレーション・`stripe` 依存・Stripe env・web `BillingPage` を撤去。Agent / resume-draft から残高チェック・クレジット消費・使用量記録の配線を剥がす。
3. **#523 マルチプロバイダ撤去**: `services/agent/llm/` から OpenAI / Gemini クライアントとプロバイダ切替を削除（**Anthropic(Vertex ADC) + Ollama のみ残す**）。`model_catalog` を Haiku 固定に縮退。`openai` / `google-genai` 依存とプロバイダ選択 UI を削除。**`anthropic[vertex]` と Anthropic 用 Vertex 設定は残す**（下記「残す Anthropic の認証方式」）。撤去する env は Gemini 用 `VERTEX_LOCATION` と OpenAI の `OPENAI_API_KEY` のみ。

### 残すもの（撤去しない不変条件）

- **ローカル Ollama 経路**（ADR-0010 の dev/prod 分離思想）
- **Agent の不変条件**（ADR-0010 / `.claude/rules/backend/agent.md`）: LLM は `services/agent/` のみ・DB 非更新原則・エラー契約（`AGENT_LLM_ERROR` / `AGENT_PARSE_ERROR`）・構造化出力（tool use スキーマ）・リトライ 1 回
- **`factory.get_llm_client()` の「切替 1 箇所」原則**（切替先が Anthropic + Ollama の 2 択に減るだけ）

### ADR-0018 / 0020（ドラフト生成）への適用

経歴書ドラフト生成（ADR-0018 → 0020 で非同期化）は `run_task.py` に課金確定を持つ。#522 でこの課金配線（事前残高チェック 402・PDF レンダリング後の実課金・課金記録失敗時の dead_letter 化）を剥がす。ドラフト生成自体・最小永続化（`resume_draft_cache`）・非同期タスク構造は維持する。

### 残す Anthropic の認証方式: Vertex AI(ADC) を維持する

マルチプロバイダ撤去後も、残る Anthropic-Haiku は **Vertex AI（Cloud Run の SA → ADC）経由を維持する**。ADR-0015 の PII データガバナンス（学習除外 + アジア圏データ所在）は、プロバイダが 1 社に減っても要件として有効なため、その認証判断を本 ADR に引き継ぐ。

- **残す**: `anthropic[vertex]` 依存 / `AsyncAnthropicVertex` 経路 / `VERTEX_ANTHROPIC_LOCATION` / `GCP_PROJECT_ID`（Cloud Tasks と共用）/ Cloud Run SA の `roles/aiplatform.user`
- **撤去する**: Gemini 用 `VERTEX_LOCATION` と `google-genai`、OpenAI の `OPENAI_API_KEY` と `openai`、および Gemini/OpenAI クライアント
- 経歴書（PII）を LLM に送るプロダクトとして、データ所在地（アジア圏）と学習除外を担保し続けることを優先する。`ANTHROPIC_API_KEY` 直キー方式には**戻さない**（データ所在地を失うため）。

これにより ADR-0015 は「Gemini の Vertex 経路・OpenAI の API キー継続・マルチプロバイダ前提」の部分が Superseded になり、「Anthropic を Vertex AI(ADC) で叩く」中核判断は本 ADR が継承する。

## 代替案

- **Sonnet 課金だけ残す**: 「壁」の本体が残る。用途（小さな JSON 生成）に Haiku で足りる以上、課金運用（Stripe / 未払いリスク）を残す利点は薄く却下。
- **レート制限なしで無料開放**: 蓋ゼロの無料 LLM エンドポイントは abuse で運営コストが青天井になり得るため却下。レート制限を前提条件にする。
- **マルチプロバイダを残す**: dev の従量課金抑制（ADR-0013 の動機）はローカル Ollama 無料パスで代替済み。品質差の選択肢は用途に対し過剰で、3 クライアント + Vertex/ADC + 複数 env の保守が勝つため却下。

## トレードオフ・既知のリスク

- **Haiku の API コストが運営持ちになる**（従来はユーザのクレジットで相殺）。安価とはいえ無料開放のため、**ユーザ単位レート制限（日次上限）が実質必須の前提条件**。順序として #521（レート制限）を #522（課金撤去）より先に入れる。
- **既存のクレジット残高データが消える**（#522 の drop マイグレーション）。破壊的変更。既存残高のユーザがいる場合はエクスポート/精算を #522 の stage で明示検討する。
- Sonnet / Gemini / GPT を選べなくなる（品質を上げたい場面での選択肢喪失）。用途が Haiku で足りる前提のトレードオフ。
- 公開 API（billing 系パス・model 選択パラメータ・課金 ErrorCode）の削除は OpenAPI 生成物・web 型に波及する破壊的変更。外部クライアント不在を前提とする。

## 将来の移行条件

- 上位モデルや課金を再導入する場合は、本 ADR を `Superseded` とした上で新規 ADR を起票し、ADR-0012 の課金設計（原子的 UPDATE・二重課金防止）を git 履歴から再評価する。
- マルチプロバイダを再導入する場合は ADR-0013 の provider 抽象を、データガバナンスを再開する場合は ADR-0015 の Vertex/ADC 設計を、それぞれ再評価する。

## 設計原則との関係

- **P1（コスト最適化を第一制約にする）**: 過剰装備（3 プロバイダ + Vertex + Stripe）の保守コストを削り、個人開発規模（ADR-0005）に構成を合わせる。
- **P6（可逆性を設計する）**: 撤退条件を明記し、git 履歴と旧 ADR から再構築可能な可逆撤去とする。
- **P2（PII を信頼境界の外に出さない）**: 残す Anthropic を Vertex AI(ADC) 経由に維持し、ADR-0015 の PII データガバナンス（学習除外 + アジア圏データ所在）を単一プロバイダ構成でも継続する。

## 関連リンク

- [#517 機能整理・体験改善ロードマップ](../../README.md)（親 issue）
- #520（本 ADR）／#521（レート制限）／#522（課金撤去）／#523（マルチプロバイダ撤去）
- [ADR-0012](0012-agent-model-switching-and-prepaid-billing.md) / [ADR-0013](0013-multi-provider-llm-selection.md) / [ADR-0015](0015-vertex-ai-for-gemini-anthropic.md)（撤去対象）
