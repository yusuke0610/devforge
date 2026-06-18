"""LLM プロバイダの切り替え（モデルエイリアス由来の provider で分岐 / ADR-0013）。

プロバイダ選択は ``model_catalog.ModelSpec.provider`` に紐づき、リクエスト単位で
切り替わる（旧来のグローバル ``LLM_PROVIDER`` は廃止）。ただし ``LLM_LOCAL_OLLAMA``
が有効なときは、選択モデルに関わらず全リクエストをローカル Ollama に通す（無料パス）。
"""

from ....core import settings
from ..model_catalog import PROVIDER_ANTHROPIC, PROVIDER_GOOGLE, PROVIDER_OPENAI
from .base import LLMClient, LLMError


def get_llm_client(provider: str) -> LLMClient:
    """provider に応じた LLM クライアントを返す。

    遅延 import により、各社 SDK 未インストール環境でも他プロバイダ／ローカル
    Ollama モード（開発・テスト）で動作できるようにする。
    """
    # ローカル開発の無料上書き: provider を無視して Ollama に通す
    if settings.use_local_ollama():
        from .ollama_client import OllamaClient

        return OllamaClient()
    if provider == PROVIDER_ANTHROPIC:
        from .anthropic_client import AnthropicClient

        return AnthropicClient()
    if provider == PROVIDER_GOOGLE:
        from .google_client import GoogleClient

        return GoogleClient()
    if provider == PROVIDER_OPENAI:
        from .openai_client import OpenAIClient

        return OpenAIClient()
    # 設定ミス・未対応値をフォールバックで隠さず fail fast にする。
    # LLMError は router で 502 + 日本語メッセージにマッピングされる
    raise LLMError(f"未対応の LLM プロバイダです: {provider}")
