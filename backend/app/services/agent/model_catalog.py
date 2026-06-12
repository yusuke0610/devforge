"""Agent で選択可能な LLM モデルのカタログ（SSoT / ADR-0012）。

クライアントはエイリアス（"haiku" / "sonnet"）のみを指定し、実モデル ID と
課金レートは本モジュールでマップする。任意のモデル文字列をクライアントから
受け付けない（コスト爆発・未検証モデルの注入を防ぐ）。

クレジット単位は「1 クレジット = $0.0001」（USD ペッグ）。消費レートは
API 原価 × マージン係数で算出する。定数の根拠は ADR-0012 を参照。
"""

import math
from dataclasses import dataclass
from typing import get_args

from ...schemas.agent import AgentModelAlias

# 1 USD あたりのクレジット数（1 クレジット = $0.0001）
CREDITS_PER_USD = 10_000
# API 原価に乗せるマージン係数（為替・キャッシュ未ヒット・運用コストのバッファ）
MARGIN_MULTIPLIER = 1.5

# Anthropic API の公表原価（USD / 100 万トークン）。改定時はここだけ直す
_HAIKU_INPUT_USD_PER_MTOK = 1.0
_HAIKU_OUTPUT_USD_PER_MTOK = 5.0
_SONNET_INPUT_USD_PER_MTOK = 3.0
_SONNET_OUTPUT_USD_PER_MTOK = 15.0


def _credits_per_mtok(usd_per_mtok: float) -> int:
    """USD/MTok の原価をマージン込みのクレジット/MTok レートに換算する。"""
    return int(usd_per_mtok * CREDITS_PER_USD * MARGIN_MULTIPLIER)


@dataclass(frozen=True)
class ModelSpec:
    """エイリアス 1 件分のモデル定義。"""

    # Anthropic API に渡す実モデル ID
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
        model_id="claude-haiku-4-5",
        is_free=True,
        input_credits_per_mtok=_credits_per_mtok(_HAIKU_INPUT_USD_PER_MTOK),
        output_credits_per_mtok=_credits_per_mtok(_HAIKU_OUTPUT_USD_PER_MTOK),
    ),
    "sonnet": ModelSpec(
        model_id="claude-sonnet-4-6",
        is_free=False,
        input_credits_per_mtok=_credits_per_mtok(_SONNET_INPUT_USD_PER_MTOK),
        output_credits_per_mtok=_credits_per_mtok(_SONNET_OUTPUT_USD_PER_MTOK),
    ),
}

# モジュールロード時にスキーマの Literal とカタログの drift を fail fast で検出する
assert set(MODEL_CATALOG) == set(get_args(AgentModelAlias)), (
    "MODEL_CATALOG のキーは schemas/agent.py の AgentModelAlias と一致させること"
)


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
