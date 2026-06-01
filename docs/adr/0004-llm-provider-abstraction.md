# ADR-0004: LLM プロバイダ抽象化（Ollama/Vertex AI）の設計判断

## ステータス

Superseded by ADR-0008

## コンテキスト

DevForge の LLM 処理（キャリア分析・GitHub 分析等）は Cloud Tasks による非同期処理で実行される。

以下の要件があった。

- ローカル開発では Vertex AI の API コストを発生させたくない
- ローカル LLM（Ollama）を試す目的もある
- 本番（Cloud Run）では GCP スタックで統一し、Workload Identity で認証を完結させたい
- SDK の変更（将来的なプロバイダ追加・切り替え）に対して呼び出し側のコードを変更したくない

## 決定内容

`services/intelligence/llm/` に以下の構成でプロバイダ抽象化を実装する。

```
services/intelligence/llm/
├── base.py           ← LLMClient（抽象基底クラス）
├── factory.py        ← get_llm_client()
├── ollama_client.py  ← OllamaClient（ローカル開発用）
└── vertex_client.py  ← VertexClient（本番 Cloud Run 用）
```

**インターフェース定義**:

```python
class LLMClient(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str: ...

    @abstractmethod
    async def check_available(self) -> bool: ...
```

**`generate()` の契約**: 失敗時も例外を投げず空文字列を返す。
GitHub 分析はスコア計算等の別軸処理と並行して動作しており、LLM エラーで処理全体が停止することを避けるための意図的な設計。

**切り替え**: `LLM_PROVIDER` 環境変数のみ。コードの分岐は `factory.py` の 1 箇所。

```python
provider = os.environ.get("LLM_PROVIDER", "ollama").lower()
if provider == "vertex":
    return VertexClient()   # Cloud Run 本番
return OllamaClient()       # ローカル開発（デフォルト）
```

**実装の詳細**:

| クラス | SDK | 接続先 |
|---|---|---|
| OllamaClient | httpx（REST直呼び） | http://localhost:11434 |
| VertexClient | google-genai | Vertex AI Gemini |

**遅延 import**: `factory.py` の関数内で各クライアントを import しているため、`google-genai` が未インストールの環境でも Ollama モードで起動可能。

**`check_available()` の非対称性**:

| クラス | 実装 |
|---|---|
| OllamaClient | `/api/tags` を叩きモデル名の存在を確認（実 HTTP 疎通） |
| VertexClient | `VERTEX_PROJECT_ID` が空でなければ `True`（疎通確認なし） |

Vertex AI は「設定されていれば動く前提」、Ollama は「起動していないケースを許容する」という設計の非対称性を意図的に持つ。

## 代替案

- **OpenAI / Anthropic API**: GCP スタックへの統一とコスト観点から対象外
- **プロバイダ抽象化なし（直接呼び出し）**: SDK 変更時に呼び出し箇所が散在するリスクがあり却下
- **LangChain 等のフレームワーク**: 軽量・シンプルな LLM 利用のため外部依存を増やさない方針で採用しなかった

## トレードオフ・既知のリスク

1. **LLM 処理失敗が UI に伝達されない**
   - `generate()` が失敗時に空文字を返す設計のため、LLM 処理が失敗してもフロントエンドでエラーとして検知できない
   - タイムアウト・モデル未起動・API エラー等の失敗原因が区別できない
   - → 別途 Issue 化する

2. **`check_available()` の非対称性**
   - VertexClient は疎通確認を行わないため、設定ミス（プロジェクトID誤り等）が起動時に検出されない

3. **プロバイダの切り替えはアプリ全体で一括**
   - 処理ごとにプロバイダを変える設計にはなっていない

## 将来の移行条件

- プロバイダを追加する場合は `LLMClient` を継承した新クライアントを追加し、`factory.py` に分岐を追加するだけでよい
- `generate()` の失敗を区別したい場合は、空文字ではなく Result 型（成功/失敗/エラー種別）を返す設計への変更を検討する

## 関連リンク

- [ADR-0004 PR](https://github.com/yusuke0610/devforge/pulls)

---

2026-05-31: LLM をサービス内で使う可能性が低くルールベース設計に統一したため、本 ADR で定義した LLM プロバイダ抽象化・関連 env・依存・ErrorCode を撤去した。詳細は [ADR-0008](0008-remove-llm-to-rule-based-design.md) を参照。
