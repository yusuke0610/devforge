"""Agent で使用する LLM モデルのカタログ（SSoT）。

ADR-0023 で Haiku 無料一本化へ縮退したため、モデルは haiku のみ。実モデル ID は
本モジュールでマップする（任意のモデル文字列をクライアントから受け付けない）。
ローカル開発は `LLM_LOCAL_OLLAMA` で Ollama に通す（ADR-0010 の dev/prod 分離）。
"""

from dataclasses import dataclass
from typing import get_args

from ...schemas.agent import AgentModelAlias

# LLM プロバイダ識別子（factory.get_llm_client の分岐キー）。本番は Anthropic のみ。
PROVIDER_ANTHROPIC = "anthropic"
_VALID_PROVIDERS = frozenset({PROVIDER_ANTHROPIC})


@dataclass(frozen=True)
class ModelSpec:
    """エイリアス 1 件分のモデル定義。"""

    # 担当プロバイダ（factory がこの値でクライアントを選ぶ）
    provider: str
    # 各プロバイダ API に渡す実モデル ID
    model_id: str


# エイリアス → モデル定義（キー集合は schemas/agent.py の AgentModelAlias と
# 一致させる。drift は test_model_catalog_matches_schema_alias で検出する）
MODEL_CATALOG: dict[str, ModelSpec] = {
    "haiku": ModelSpec(
        provider=PROVIDER_ANTHROPIC,
        # Vertex AI の Anthropic model id は版指定が要る（@日付）。
        # Haiku 4.5 は @20251001 が必須（ADR-0015 / Vertex Model Garden 正本）
        model_id="claude-haiku-4-5@20251001",
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
