"""GitHub Linguist 由来の言語正規化（ADR-0016 discover / D3・D4）。

GitHub の ``/languages`` API が返す言語名は既に Linguist の正規名なので、本モジュールは
**外部を叩かず**内部マスタ（``resources/linguist_master.json``）へ resolve するだけに徹する。

責務:
  - エイリアス → 正規名の名寄せ
  - ``group`` → parent への写像
  - data/prose 型言語の既定除外（``keep_data`` で補正）と明示除外（``exclude``）
  - 表示名の補正（例: ``HCL`` → ``Terraform`` / ``Dockerfile`` → ``Docker``）

マスタは languages.yml の定期バッチ取り込みで再生成する想定の暫定キュレーション。
マスタ未収録の言語は「programming とみなして採用」にフォールバックし、新言語の取りこぼしを防ぐ
（ノイズは ``exclude`` 側で制御する）。
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_MASTER_PATH = Path(__file__).parent / "resources" / "linguist_master.json"

# 既定で除外する Linguist の type（経歴書のスキルとして不適なカテゴリ）。
_EXCLUDED_TYPES = frozenset({"data", "prose"})


@dataclass(frozen=True)
class ResolvedLanguage:
    """マスタへ resolve 済みの言語。"""

    canonical: str  # Linguist の正規名（例: "TypeScript"）
    display: str  # 表示名の補正後（例: HCL → "Terraform"）
    parent: str | None  # Linguist の group（例: なし）


@dataclass(frozen=True)
class _Master:
    languages: dict[str, dict]
    exclude: frozenset[str]
    keep_data: frozenset[str]
    alias_index: dict[str, str]  # lower(alias|name) → canonical


@lru_cache(maxsize=1)
def _load_master() -> _Master:
    raw = json.loads(_MASTER_PATH.read_text(encoding="utf-8"))
    languages: dict[str, dict] = raw.get("languages", {})
    alias_index: dict[str, str] = {}
    for canonical, entry in languages.items():
        alias_index[canonical.lower()] = canonical
        for alias in entry.get("aliases", []):
            alias_index.setdefault(alias.lower(), canonical)
    return _Master(
        languages=languages,
        exclude=frozenset(raw.get("exclude", [])),
        keep_data=frozenset(raw.get("keep_data", [])),
        alias_index=alias_index,
    )


def resolve_language(name: str) -> ResolvedLanguage | None:
    """言語名を内部マスタへ resolve する。除外対象なら ``None`` を返す。

    Args:
        name: GitHub ``/languages`` が返す言語名（Linguist 正規名）またはエイリアス。

    Returns:
        採用する言語は ``ResolvedLanguage``、除外する言語は ``None``。
    """
    if not name:
        return None
    master = _load_master()
    canonical = master.alias_index.get(name.lower(), name)

    # 明示除外（HTML/CSS 等のノイズ）はマスタ収録の有無に関わらず弾く。
    if canonical in master.exclude:
        return None

    entry = master.languages.get(canonical)
    if entry is None:
        # マスタ未収録は programming とみなして採用（取りこぼし防止）。
        return ResolvedLanguage(canonical=canonical, display=canonical, parent=None)

    # data/prose 型は既定除外。keep_data に挙げたものだけ補正で残す。
    if entry.get("type") in _EXCLUDED_TYPES and canonical not in master.keep_data:
        return None

    return ResolvedLanguage(
        canonical=canonical,
        display=entry.get("display") or canonical,
        parent=entry.get("group"),
    )
