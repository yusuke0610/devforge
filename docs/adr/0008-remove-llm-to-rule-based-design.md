# ADR-0008: LLM プロバイダ抽象化の撤去とルールベース設計への統一

## ステータス

Superseded by ADR-0010

## コンテキスト

ADR-0004 で LLM プロバイダ抽象化（Ollama / Vertex AI、`services/intelligence/llm/`）を導入したが、その後の方針転換により状況が変わった。

- LLM を利用していた機能（キャリア分析 AI・職務経歴書 PDF の AI 抽出）は既に削除済みで、現在のサービスはルールベース（決定論的パイプライン）設計に統一されている。
- 残った `services/intelligence/llm/`（OllamaClient / VertexClient / factory）は本番フロー（ルーター・タスクハンドラ・サービス）から一切呼ばれておらず、参照はテストとゴーストスクリプトのみの **休眠コード**になっている。
- 付随して、LLM 用環境変数 7 種（`LLM_PROVIDER` / `VERTEX_*` / `OLLAMA_*`）、`google-genai` 依存、LLM 用 ErrorCode（`LLM_TIMEOUT` / `LLM_UNAVAILABLE`）、サニタイザ・プロンプトローダ・`app/prompts/` も発火元を失った dead code として残存している。
- 今後 LLM をサービス内で使う可能性は低いと判断した。

休眠コードを残すと、依存の脆弱性追従コスト・誤った「使われている」前提・env 同期の負担が積み上がる。

## 決定内容

LLM プロバイダ抽象化と関連資産を全て撤去し、ルールベース設計に一本化する。

撤去対象:

- **コード**: `services/intelligence/llm/`、`services/llm/`（サニタイザ）、`utils/prompt_loader.py`、`app/prompts/`、`scripts/measure_career_analysis.py`、`settings.py` の LLM ゲッター 4 関数
- **環境変数**: `LLM_PROVIDER` / `VERTEX_PROJECT_ID` / `VERTEX_LOCATION` / `VERTEX_MODEL` / `OLLAMA_BASE_URL` / `OLLAMA_MODEL` / `OLLAMA_TIMEOUT`（env_keys.py / cloud_run / docker-compose / docs/api.md / conftest.py から削除）
- **依存**: `google-genai`
- **ErrorCode**: `LLM_TIMEOUT` / `LLM_UNAVAILABLE`（backend errors.py の enum・分類ロジック、frontend の errorCodes.ts / errorMessages.ts）
- **ルール**: `.claude/rules/backend/llm.md`

これに伴い ADR-0004 を `Superseded by ADR-0008` とする。

## 代替案

- **休眠のまま温存する**: 将来 LLM を使う余地を残せるが、未使用コードの保守・依存追従コストが継続し、`generate()` が失敗時に空文字を返す既知のリスク（ADR-0004）も塩漬けになる。利用見込みが低い以上、温存の利点は薄いと判断し却下。
- **コードだけ消して env / ErrorCode は残す**: 中途半端な dead code が残り、env 同期ルール（4+1 箇所）の対象に居座る。完全撤去の方が状態が単純になるため却下。

## トレードオフ・既知のリスク

- 将来 LLM を再導入する場合は、抽象化層・env・依存をゼロから再構築する必要がある（ただし git 履歴と ADR-0004 から設計を復元可能）。
- 公開 ErrorCode 2 種の削除は OpenAPI 生成物・フロントエンドの型 union に波及する破壊的変更。外部にこの API を消費するクライアントがいないことを前提とする。

## 将来の移行条件

- LLM 利用を再開する場合は、本 ADR を `Superseded` とした上で新規 ADR を起票し、ADR-0004 の設計（プロバイダ抽象化・`generate()` の契約）を再評価して再構築する。
- その際は ADR-0004 で積み残した「LLM 失敗を UI に伝達できない」「`check_available()` の非対称性」を設計段階で解消すること。

## 関連リンク

- [ADR-0004: LLM プロバイダ抽象化（Ollama/Vertex AI）の設計判断](0004-llm-provider-abstraction.md)
- [ADR-0010: DevForge Agent 機能の導入](0010-devforge-agent.md)（本 ADR を Superseded とし LLM を再導入）

---

2026-06-11: DevForge Agent（対話型キャリア戦略支援）の導入に伴い LLM を再導入したため、本 ADR の「将来の移行条件」に従い [ADR-0010](0010-devforge-agent.md) で Superseded とした。
