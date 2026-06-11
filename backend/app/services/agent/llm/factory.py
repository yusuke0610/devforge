"""LLM プロバイダの切り替え（LLM_PROVIDER 環境変数で分岐）。"""

from ....core import settings
from .base import LLMClient, LLMError


def get_llm_client() -> LLMClient:
    """設定に応じた LLM クライアントを返す。

    遅延 import により、anthropic SDK 未インストール環境でも
    ollama モード（ローカル開発・テスト）で動作できるようにする。
    """
    provider = settings.get_llm_provider()
    if provider == "anthropic":
        from .anthropic_client import AnthropicClient

        return AnthropicClient()
    if provider == "ollama":
        from .ollama_client import OllamaClient

        return OllamaClient()
    # 設定ミス（"openai" 等）をフォールバックで隠さず fail fast にする。
    # LLMError は router で 502 + 日本語メッセージにマッピングされる
    raise LLMError(f"未対応の LLM_PROVIDER です: {provider}")
