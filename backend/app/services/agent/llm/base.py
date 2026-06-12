"""LLM クライアントの抽象基底クラスと共通例外。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(Exception):
    """LLM 呼び出しの失敗（タイムアウト / 接続エラー / HTTP エラー）を表す。

    プロバイダ固有の例外は各クライアントで本例外にラップする。
    呼び出し側（router）は本例外を 502 + ``AGENT_LLM_ERROR`` にマッピングする。
    """


@dataclass(frozen=True)
class LLMResult:
    """LLM 1 回呼び出しの結果（応答テキスト + 実トークン使用量）。

    トークン数はクレジット課金（ADR-0012）の根拠となる実測値。
    使用量を返せないプロバイダ（Ollama 等のローカル実装）は 0 を返す。
    """

    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(ABC):
    """LLM プロバイダの共通インターフェース。

    失敗時は例外を握りつぶさず ``LLMError`` を raise する契約
    （ADR-0004 の「空文字を返す」設計は採用しない。ADR-0010 参照）。
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        output_schema: dict,
        model_id: str,
    ) -> LLMResult:
        """system プロンプトと会話 messages を渡して構造化応答と使用量を返す。

        messages は ``[{"role": "user" | "assistant", "content": str}, ...]`` で、
        末尾が今回の user プロンプト（マルチターン時は先頭側に履歴が並ぶ）。
        output_schema は応答が従うべき JSON Schema（output_schema.py で構築）。
        各プロバイダの構造化出力機構（Anthropic: tool use 強制 / Ollama: format）
        に渡し、``LLMResult.text`` はスキーマに従う JSON のシリアライズ文字列とする。
        model_id は model_catalog.py が解決した実モデル ID（Anthropic 用）。
        自前のモデル設定を持つプロバイダ（Ollama）は無視してよい。

        Raises:
            LLMError: タイムアウト・接続失敗・API エラー時。
        """
