"""LLM プロバイダの切り替え（モデルエイリアス由来の provider で分岐）。

ADR-0023 で Haiku 無料一本化へ縮退したため、本番プロバイダは Anthropic のみ。
``LLM_LOCAL_OLLAMA`` が有効なときは、選択モデルに関わらず全リクエストをローカル
Ollama に通す（ADR-0010 の dev/prod 分離。無料パス）。
"""

from ....core import settings
from ..model_catalog import PROVIDER_ANTHROPIC
from .base import LLMClient, LLMError


def get_llm_client(provider: str) -> LLMClient:
    """provider に応じた LLM クライアントを返す。

    遅延 import により、SDK 未インストール環境でもローカル Ollama モード
    （開発・テスト）で動作できるようにする。
    """
    # ローカル開発の無料上書き: provider を無視して Ollama に通す
    if settings.use_local_ollama():
        from .ollama_client import OllamaClient

        return OllamaClient()
    if provider == PROVIDER_ANTHROPIC:
        from .anthropic_client import AnthropicClient

        return AnthropicClient()
    # 設定ミス・未対応値をフォールバックで隠さず fail fast にする。
    # LLMError は router で 502 + 日本語メッセージにマッピングされる
    raise LLMError(f"未対応の LLM プロバイダです: {provider}")
