"""LLM クライアントの抽象基底クラスと共通例外。

``AgentUsage`` / ``AgentResponseParseError`` は本来 LLM 呼び出し結果の解釈（response
parsing）に属する概念だが、chat_service / resume_draft / resume_import / skill_display の
4 モジュールが共通のリトライヘルパー（``llm/retry.py``）経由でこれらを扱うため、
双方向 import（chat_service → llm.retry → chat_service）を避ける目的でここに置く
（chat_service.py は後方互換のため re-export する）。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ....schemas.agent import AgentModelAlias

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentUsage:
    """LLM 呼び出し 1 回分の実トークン使用量（リトライ分を含む合算）。

    ADR-0023 で課金を撤去したため現在は消費されないが、将来の観測・計測用に
    トークン計上インフラとして温存する。呼び出し元（chat_service /
    resume_draft / resume_import / skill_display）は DB に触れない原則を維持する。
    """

    model: AgentModelAlias
    input_tokens: int
    output_tokens: int


class LLMError(Exception):
    """LLM 呼び出しの失敗（タイムアウト / 接続エラー / HTTP エラー）を表す。

    プロバイダ固有の例外は各クライアントで本例外にラップする。
    呼び出し側（router）は本例外を 502 + ``AGENT_LLM_ERROR`` にマッピングする。

    リトライ前の試行で消費済みトークンがある状態で本例外が起きた場合、課金漏れを
    防ぐため確定済みの使用量を ``usage`` に載せて伝播する（chat_service が設定 /
    ADR-0012）。通常の発生時（消費前の失敗）は ``None``。
    """

    def __init__(self, message: str = "", *, usage: AgentUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


class AgentResponseParseError(Exception):
    """LLM 応答の JSON パースまたはスキーマ検証に失敗。

    リトライ後も失敗した場合、確定済みの使用量を ``usage`` に載せて呼び出し元（router）へ
    伝播する（観測用。ADR-0023 で課金は撤去）。パース前段（リトライ未到達）の失敗では ``usage`` は None。
    """

    def __init__(self, message: str, *, usage: AgentUsage | None = None) -> None:
        super().__init__(message)
        self.usage = usage


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


# 各プロバイダクライアントが共有する LLMError 契約（502 にマップされる）のヘルパ。
# メッセージ・ログ形式を 1 箇所に集約し、クライアント間でのドリフトを防ぐ（ADR-0013）。


def require_api_key(value: str, label: str) -> str:
    """API キーの空判定を一元化する。空なら LLMError、非空ならそのまま返す。

    label は環境変数名（例: ``ANTHROPIC_API_KEY``）。値そのものはログ・例外に含めない。
    """
    if not value:
        raise LLMError(f"{label} が設定されていません")
    return value


def require_gcp_project(value: str) -> str:
    """Vertex AI クライアント（Anthropic）の GCP プロジェクト ID を検証する。

    Vertex 経由のプロバイダは API キーの代わりに SA(ADC) + プロジェクト ID で認証する
    （ADR-0015）。空なら LLMError、非空ならそのまま返す。ローカルは LLM_LOCAL_OLLAMA で
    Vertex クライアントを生成しないため、この検証は本番（Cloud Run）経路でのみ効く。
    """
    if not value:
        raise LLMError("GCP_PROJECT_ID が設定されていません")
    return value


def wrap_api_error(provider: str, exc: Exception) -> "LLMError":
    """プロバイダ SDK 例外を LLMError へ変換する（ログ + 整形）。

    呼び出し側の except 内で ``raise wrap_api_error("Google", exc) from exc`` の形で使う。
    捕捉する SDK 例外型は各クライアントで異なるため try/except 自体は共通化しない。
    API キー等の秘密情報を載せないよう、ログ・メッセージには例外型名のみを含める。
    """
    logger.warning("%s API 呼び出しに失敗: %s", provider, type(exc).__name__)
    return LLMError(f"{provider} API error: {type(exc).__name__}")


def require_text(provider: str, text: str | None) -> str:
    """空応答ガードを一元化する。空（None / 空文字）なら LLMError、非空なら返す。"""
    if not text:
        raise LLMError(f"{provider} API が空の応答を返しました")
    return text
