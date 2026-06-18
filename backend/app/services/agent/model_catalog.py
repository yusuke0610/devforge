"""Agent で選択可能な LLM モデルのカタログ（SSoT / ADR-0012）。

クライアントはエイリアス（"haiku" / "sonnet"）のみを指定し、実モデル ID と
課金レートは本モジュールでマップする。任意のモデル文字列をクライアントから
受け付けない（コスト爆発・未検証モデルの注入を防ぐ）。

クレジット単位は「1 クレジット = ¥1」（円ペッグ）。消費レートは API 原価（USD）を
円換算し、マージン係数を乗じて算出する。為替変動は YEN_PER_USD の調整で吸収する。
定数の根拠は ADR-0012 を参照。
"""

import math
from dataclasses import dataclass
from typing import get_args

from ...schemas.agent import AgentModelAlias

# 1 クレジットあたりの円換算（1 クレジット = ¥1）。クライアント表示の正本
YEN_PER_CREDIT = 1
# 円換算に使う想定為替（USD→JPY）。為替変動はここの調整で吸収する
YEN_PER_USD = 150
# API 原価に乗せるマージン係数（為替変動・キャッシュ未ヒット・運用コストのバッファ）
MARGIN_MULTIPLIER = 1.5

# 各社 API の公表原価（USD / 100 万トークン）。改定時はここだけ直す。
# Anthropic
_HAIKU_INPUT_USD_PER_MTOK = 1.0
_HAIKU_OUTPUT_USD_PER_MTOK = 5.0
_SONNET_INPUT_USD_PER_MTOK = 3.0
_SONNET_OUTPUT_USD_PER_MTOK = 15.0
# Google Gemini 2.5（ADR-0013）
_GEMINI_FLASH_INPUT_USD_PER_MTOK = 0.30
_GEMINI_FLASH_OUTPUT_USD_PER_MTOK = 2.50
_GEMINI_PRO_INPUT_USD_PER_MTOK = 1.25
_GEMINI_PRO_OUTPUT_USD_PER_MTOK = 10.0
# OpenAI GPT（ADR-0013）。gpt-mini = 廉価（gpt-4o-mini 系）、gpt = 高級（GPT-4.1/5 系）
_GPT_MINI_INPUT_USD_PER_MTOK = 0.15
_GPT_MINI_OUTPUT_USD_PER_MTOK = 0.60
_GPT_INPUT_USD_PER_MTOK = 2.0
_GPT_OUTPUT_USD_PER_MTOK = 8.0

# LLM プロバイダ識別子（factory.get_llm_client の分岐キー / ADR-0013）
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GOOGLE = "google"
PROVIDER_OPENAI = "openai"
_VALID_PROVIDERS = frozenset({PROVIDER_ANTHROPIC, PROVIDER_GOOGLE, PROVIDER_OPENAI})

# 「N クレジットで平均M回」「約N回」の目安に使う標準的な 1 回の消費トークン。
# Agent はシステムプロンプト + レジュメ + 参照 + 履歴で入力が大きいため、入力多めの
# 概算を置く。利用実績ゼロの新規ユーザー向けのフォールバック（実消費は
# agent_usage_logs の実測値で算出。本値は概算で、実データに合わせて調整可）
BASELINE_INPUT_TOKENS = 10_000
BASELINE_OUTPUT_TOKENS = 1_500


def _credits_per_mtok(usd_per_mtok: float) -> int:
    """USD/MTok の原価を、マージン込みのクレジット/MTok レート（円ペッグ）に換算する。"""
    yen_per_mtok = usd_per_mtok * YEN_PER_USD * MARGIN_MULTIPLIER
    return round(yen_per_mtok / YEN_PER_CREDIT)


@dataclass(frozen=True)
class ModelSpec:
    """エイリアス 1 件分のモデル定義。"""

    # 担当プロバイダ（factory がこの値でクライアントを選ぶ / ADR-0013）
    provider: str
    # 各プロバイダ API に渡す実モデル ID
    model_id: str
    # True なら残高チェック・クレジット消費を行わない（使用ログのみ記録）
    is_free: bool
    # マージン込みの消費レート（クレジット / 100 万トークン）
    input_credits_per_mtok: int
    output_credits_per_mtok: int


# エイリアス → モデル定義（キー集合は schemas/agent.py の AgentModelAlias と
# 一致させる。drift は test_model_catalog_matches_schema_alias で検出する）
MODEL_CATALOG: dict[str, ModelSpec] = {
    "haiku": ModelSpec(
        provider=PROVIDER_ANTHROPIC,
        model_id="claude-haiku-4-5",
        is_free=True,
        input_credits_per_mtok=_credits_per_mtok(_HAIKU_INPUT_USD_PER_MTOK),
        output_credits_per_mtok=_credits_per_mtok(_HAIKU_OUTPUT_USD_PER_MTOK),
    ),
    "sonnet": ModelSpec(
        provider=PROVIDER_ANTHROPIC,
        model_id="claude-sonnet-4-6",
        is_free=False,
        input_credits_per_mtok=_credits_per_mtok(_SONNET_INPUT_USD_PER_MTOK),
        output_credits_per_mtok=_credits_per_mtok(_SONNET_OUTPUT_USD_PER_MTOK),
    ),
    "gemini-flash": ModelSpec(
        provider=PROVIDER_GOOGLE,
        model_id="gemini-2.5-flash",
        # 低単価のため無料枠として開放（実 API 原価は運営が負担 / ADR-0013）
        is_free=True,
        input_credits_per_mtok=_credits_per_mtok(_GEMINI_FLASH_INPUT_USD_PER_MTOK),
        output_credits_per_mtok=_credits_per_mtok(_GEMINI_FLASH_OUTPUT_USD_PER_MTOK),
    ),
    "gemini-pro": ModelSpec(
        provider=PROVIDER_GOOGLE,
        model_id="gemini-2.5-pro",
        is_free=False,
        input_credits_per_mtok=_credits_per_mtok(_GEMINI_PRO_INPUT_USD_PER_MTOK),
        output_credits_per_mtok=_credits_per_mtok(_GEMINI_PRO_OUTPUT_USD_PER_MTOK),
    ),
    "gpt-mini": ModelSpec(
        provider=PROVIDER_OPENAI,
        model_id="gpt-4o-mini",
        # 低単価のため無料枠として開放（実 API 原価は運営が負担 / ADR-0013）
        is_free=True,
        input_credits_per_mtok=_credits_per_mtok(_GPT_MINI_INPUT_USD_PER_MTOK),
        output_credits_per_mtok=_credits_per_mtok(_GPT_MINI_OUTPUT_USD_PER_MTOK),
    ),
    "gpt": ModelSpec(
        provider=PROVIDER_OPENAI,
        model_id="gpt-4.1",
        is_free=False,
        input_credits_per_mtok=_credits_per_mtok(_GPT_INPUT_USD_PER_MTOK),
        output_credits_per_mtok=_credits_per_mtok(_GPT_OUTPUT_USD_PER_MTOK),
    ),
}

# モジュールロード時にスキーマの Literal とカタログの drift を fail fast で検出する。
# assert は -O / PYTHONOPTIMIZE で除去されるため、不変条件は明示的に raise する
if set(MODEL_CATALOG) != set(get_args(AgentModelAlias)):
    raise RuntimeError(
        "MODEL_CATALOG のキーは schemas/agent.py の AgentModelAlias と一致させること"
    )

# 各 spec の provider が既知の識別子であることを保証する（タイポ・未対応値の早期検出）
_invalid_providers = {
    alias: spec.provider
    for alias, spec in MODEL_CATALOG.items()
    if spec.provider not in _VALID_PROVIDERS
}
if _invalid_providers:
    raise RuntimeError(f"MODEL_CATALOG に未対応の provider があります: {_invalid_providers}")


def get_model_spec(alias: str) -> ModelSpec:
    """エイリアスからモデル定義を返す。未知のエイリアスは KeyError（スキーマで検証済み前提）。"""
    return MODEL_CATALOG[alias]


def calculate_credit_cost(alias: str, input_tokens: int, output_tokens: int) -> int:
    """実トークン数からクレジット消費量を算出する。無料モデルは常に 0。

    端数は切り上げ（ceil）とし、課金対象の利用で 0 クレジットにならないようにする。
    """
    spec = get_model_spec(alias)
    if spec.is_free:
        return 0
    raw = (
        input_tokens * spec.input_credits_per_mtok
        + output_tokens * spec.output_credits_per_mtok
    )
    return math.ceil(raw / 1_000_000)


def baseline_credits_per_chat(alias: str) -> int:
    """標準的な 1 回のチャットの消費クレジット（回数目安用 / ADR-0012）。

    利用実績ゼロの新規ユーザーでも「N クレジットで約M回」を出すための概算。
    無料モデルは 0。
    """
    return calculate_credit_cost(alias, BASELINE_INPUT_TOKENS, BASELINE_OUTPUT_TOKENS)
