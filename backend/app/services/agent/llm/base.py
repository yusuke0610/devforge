"""LLM クライアントの抽象基底クラスと共通例外。"""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """LLM 呼び出しの失敗（タイムアウト / 接続エラー / HTTP エラー）を表す。

    プロバイダ固有の例外は各クライアントで本例外にラップする。
    呼び出し側（router）は本例外を 502 + ``AGENT_LLM_ERROR`` にマッピングする。
    """


class LLMClient(ABC):
    """LLM プロバイダの共通インターフェース。

    失敗時は例外を握りつぶさず ``LLMError`` を raise する契約
    （ADR-0004 の「空文字を返す」設計は採用しない。ADR-0010 参照）。
    """

    @abstractmethod
    async def generate(self, system_prompt: str, messages: list[dict[str, str]]) -> str:
        """system プロンプトと会話 messages を渡して応答テキストを返す。

        messages は ``[{"role": "user" | "assistant", "content": str}, ...]`` で、
        末尾が今回の user プロンプト（マルチターン時は先頭側に履歴が並ぶ）。

        Raises:
            LLMError: タイムアウト・接続失敗・API エラー時。
        """
