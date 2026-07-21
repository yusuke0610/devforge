# ADR-0013: マルチプロバイダ LLM（ユーザー選択式）

## ステータス

Superseded by ADR-0023

## コンテキスト

DevForge Agent（ADR-0010）の LLM プロバイダは、グローバル環境変数 `LLM_PROVIDER`
（`anthropic` / `ollama`）でデプロイ単位に固定されていた。モデルエイリアス（`haiku` /
`sonnet`、ADR-0012）はリクエスト単位で選べるが、実体は Anthropic に固定だった。

2 つの要求が生じた:

1. **dev の従量課金を抑えたい** — 動作確認のたびに Anthropic へ実課金される。Gemini 2.5
   Flash は Anthropic Haiku の約 1/10 単価で、dev での確認コストを大幅に下げられる。
2. **プロバイダ選択肢を増やしたい** — 品質・コスト・構造化出力の厳格さを用途で選べるよう
   Gemini（Flash/Pro）・OpenAI GPT（廉価/高級）も使えるようにしたい。ユーザーが UI で
   都度モデルを選べる粒度が必要。

リリース前のため後方互換の負担は小さく、プロバイダ抽象の作り直しを許容できる。

## 決定内容

**プロバイダをモデルエイリアスの属性に移す。** `model_catalog.ModelSpec` に `provider`
（`anthropic` / `google` / `openai`）を持たせ、`factory.get_llm_client(provider)` が
クライアントを選ぶ。`chat_service` は選択エイリアスから provider を解決して渡す。
グローバルな `LLM_PROVIDER` は廃止する。「プロバイダ切替は factory の 1 箇所」という
ADR-0010 の原則は維持する（切替キーがグローバル env → alias 由来 provider に変わるだけ）。

- **モデル**: `gemini-flash`（gemini-2.5-flash）/ `gemini-pro`（gemini-2.5-pro）/
  `gpt-mini`（gpt-4o-mini）/ `gpt`（gpt-4.1）を catalog に追加。実モデル ID・課金レートは
  catalog が SSoT。
- **課金**: 実トークン数 × プロバイダ別レートでクレジット減算（ADR-0012 の仕組みをそのまま
  使う）。低単価モデル（`haiku` / `gemini-flash` / `gpt-mini`）は**無料枠**として開放し、実 API
  原価は運営が負担する。上位モデル（`sonnet` / `gemini-pro` / `gpt`）は有料（`is_free=False`）。
- **構造化出力**: 3 方式すべて `output_schema.py` 由来。Anthropic は tool use、Gemini は
  `response_schema`、OpenAI は strict `response_format`。後者 2 つは `oneOf` / `const` /
  `maxLength` を受け付けないため、`to_portable_schema` で `field` を `enum` に畳み、上限を
  除去した移植スキーマを使う（上限の実強制は `chat_service._parse_response` が担う二重防衛）。
- **ローカル無料パス**: `LLM_LOCAL_OLLAMA=1` が有効なら provider に関わらず Ollama に通す。
  Ollama はトークン 0 を返すためクレジットも 0。dev で実 API 課金なしに確認できる。
- **本番 Secret**: Gemini / OpenAI の API キーは Secret Manager で管理し、Cloud Run へは
  `enable_extra_llm_providers=true` の環境でのみ注入する（未投入でもデプロイをブロックしない）。

## 代替案

- **グローバル env でプロバイダ切替を維持**: 実装は最小だが「ユーザーが UI で都度選ぶ」要求を
  満たせず却下。
- **新プロバイダを Ollama 同様に model_id 無視で固定モデル運用**: 課金レートとモデルの対応が
  曖昧になり、ユーザー選択式と両立しないため却下。

## トレードオフ・既知のリスク

- **構造化出力の移植性**: Gemini / OpenAI strict は JSON Schema のサブセットしか受け付けない。
  `to_portable_schema` で吸収するが、各プロバイダ × 全スコープでの実挙動確認が必要。
- **`get_llm_client()` シグネチャ変更**: factory / chat_service / テストの注入箇所を一括更新する
  必要がある。
- **価格の鮮度**: catalog の USD レートは手動更新（為替・改定は定数 1 箇所で吸収）。
- **新 SDK のサプライチェーン**: `google-genai` / `openai` を追加。`pip-audit` で監査する。

## 将来の移行条件

- いずれかのプロバイダが恒常的に低品質・不安定なら catalog から外す。
- 構造化出力の移植が破綻するプロバイダが出たら、そのクライアントで個別スキーマ生成に切り替える。

## 関連リンク

- ADR-0010（DevForge Agent）/ ADR-0012（モデル切り替えとプリペイド課金）
- `backend/app/services/agent/llm/`（factory / 各 client）・`model_catalog.py`・`output_schema.py`

---

2026-07-22: 機能整理（#517）でプリペイド課金・マルチプロバイダを撤去し Haiku 無料一本化 + レート制限へ縮退したため、[ADR-0023](0023-remove-billing-multiprovider.md) で Superseded とした。
