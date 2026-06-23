# ADR-0015: Gemini / Anthropic を Vertex AI（SA→ADC）経由にする

## ステータス

Accepted

（ADR-0013 の認証部分「Gemini / OpenAI の API キーを Secret Manager で管理し Cloud Run に注入する」を更新する。プロバイダ抽象・モデルエイリアス・課金の仕組みは ADR-0013 を踏襲。）

## コンテキスト

DevForge Agent（ADR-0010/0013）は 3 プロバイダ（Anthropic / Gemini / OpenAI）を**すべて API キー方式**で叩いていた。キーは Secret Manager に保管し Cloud Run に注入していた（`ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` / `OPENAI_API_KEY`）。

職務経歴書（PII）を LLM に送るプロダクトとして、データガバナンスを見直した:

- **Gemini Developer API の無料枠は、送信内容がモデル学習・人手レビューに使われ得る。** PII を扱う本番では使えない。
- 一方 **Anthropic API / OpenAI API / Vertex AI はいずれも送信内容を学習に使わない**（コンシューマ製品の Claude.ai / ChatGPT とは別契約）。
- Gemini Developer API は有料枠に上げれば学習除外になるが、その場合「API キー（有料）vs Vertex AI」の比較になる。学習リスクが消えると、残る差分（シークレット管理・IAM・監査ログ・GCP 請求統合）は**すべて Vertex AI + SA(ADC) が有利**。
- **Anthropic も GCP の Vertex AI Model Garden 経由で SA 認証できる**（`AnthropicVertex`）。OpenAI のみ GCP に存在せず（クラウドパートナーは Azure）、API キーが必須。

Cloud Run の SA には `roles/aiplatform.user` が既に付与済みで、IAM 追加なしに Vertex を叩ける状態だった。

## 決定内容

**Gemini と Anthropic を Vertex AI（Cloud Run の SA → ADC）経由に切り替える。OpenAI のみ API キーを継続する。**

- **認証**: API キーの代わりに ADC（Cloud Run の SA）を使う。プロジェクト ID は Cloud Tasks と共用の `GCP_PROJECT_ID`。`ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` は廃止し、Secret Manager への注入も停止する。
- **SDK**: 既存のまま。`google-genai` は `genai.Client(vertexai=True, project, location)`、`anthropic` は `AsyncAnthropicVertex(project_id, region)`。`anthropic[vertex]` extra で ADC 用の `google-auth` を引き込む。`generate()` のロジック（構造化出力・tool use・usage 抽出）は無変更。
- **ロケーション（provider 別）**:
  - Gemini: `asia-northeast1`（Tokyo）。データを日本に留める。`VERTEX_LOCATION` で上書き可。
  - Claude: `asia-southeast1`（Singapore）。Claude は Tokyo で提供されないため最寄りの regional endpoint。`VERTEX_ANTHROPIC_LOCATION` で上書き可。データはアジア圏に留まる。
- **モデル ID**（`model_catalog.py`）: Gemini は `gemini-2.5-flash` / `gemini-2.5-pro` で Vertex でも同一。Anthropic は Vertex 形式に合わせ Haiku のみ `claude-haiku-4-5@20251001`（版指定必須）、Sonnet 4.6 は `claude-sonnet-4-6`（版指定不要）。課金レート・`is_free`・エイリアスは無変更。
- **ローカル/CI**: ローカルは `LLM_LOCAL_OLLAMA=1` で Vertex クライアントを生成しないため ADC 不要。テストは SDK をモックするため CI も ADC・キー不要。実 Vertex をローカルで叩く場合のみ `gcloud auth application-default login`。
- **`enable_extra_llm_providers`**: OpenAI キー注入のみを gate する意味に狭める（Gemini/Anthropic はキー注入が消えたため）。変数名は据え置き。

## 代替案

- **Gemini を有料 API キー（Developer API）のまま使う**: コード変更ゼロで学習除外は満たせるが、シークレット管理・IAM・監査ログ・請求が Vertex に劣る。Cloud Run 本番として Vertex を選択。
- **Anthropic も API キーのまま残す**: リージョン制約（Tokyo 未提供）を回避できるが、シークレットを 2 本残す。SA 認証できるものは寄せる方針で却下。OpenAI のみキーを残す。
- **Claude を global / multi-region endpoint で叩く**: 可用性最良・課金プレミアム無し。ただしデータ所在地の保証が弱い。PII 重視で regional（Singapore）を選択。

## トレードオフ・既知のリスク

- **regional endpoint の +10% 課金**: Claude の regional/multi-region endpoint は global 比 +10%。`model_catalog` の Anthropic 原価レートは現状 global 想定のままで、必要なら実績に合わせ調整する。
- **クロスリージョンのレイテンシ**: Claude のみ Singapore のため Cloud Run(Tokyo) からのレイテンシが Gemini より増える。許容範囲の想定。
- **Anthropic on Vertex のモデル可用性**: `asia-southeast1` での Claude 提供と model id（版）は Model Garden が正本。提供が無ければ region 再検討（global 等）。
- **無料枠の喪失**: ADR-0013 の「dev 無料確認」動機（Gemini Flash 無料枠）は Vertex では消える。dev 確認は Ollama 無料パスで吸収する。
- **未使用シークレットの残置**: `anthropic-api-key` / `google-api-key` の Secret Manager コンテナは注入停止のみ行い、削除は別 PR で全環境の設定除外を確認後に実施（破壊的操作の分離）。

## 将来の移行条件

- Claude が `asia-northeast1` で提供されたら Gemini と同一リージョンに統合する。
- データ所在地要件が緩和されれば、可用性と課金で有利な global endpoint への切り替えを検討する。
- OpenAI が GCP で SA 認証可能になれば、キーを完全に廃止する。

## 関連リンク

- ADR-0010（DevForge Agent）/ ADR-0012（モデル切り替えとプリペイド課金）/ ADR-0013（マルチプロバイダ LLM）
- `backend/app/services/agent/llm/{google_client,anthropic_client,base}.py` / `model_catalog.py`
- `backend/app/core/{settings,env_keys}.py` / `infra/modules/cloud_run/main.tf`
- [Claude on Vertex AI（model id 一覧）](https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai)
- [Anthropic Claude models | Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/partner-models/claude)
