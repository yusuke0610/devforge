"""LLM プロバイダ抽象（ADR-0010 で再構築。設計の参考: ADR-0004）。

ADR-0004 との差分: ``generate()`` は失敗時に空文字を返さず ``LLMError`` を raise する。
対話型機能のため、失敗をユーザーへ日本語エラーとして伝達する必要がある。
"""

from .base import LLMClient, LLMError
from .factory import get_llm_client

__all__ = ["LLMClient", "LLMError", "get_llm_client"]
