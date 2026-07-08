"""Python import スキャナ（ecosystem=pypi / D6）。

``import X`` / ``from X import ...`` のトップレベルモジュール名を抽出する。
pypi の package ID と import 名はしばしば異なる（PyYAML→yaml 等）。まず ``canonical_name`` の
``-``/``.``→``_`` 変換で機械的に照合し、当たらない既知の乖離のみ内部マスタ
（``resources/pypi_import_aliases.json`` / #477）で補正する。マスタ未収録の乖離は
引き続き false negative として受容する（辞書はホットパス外で生成し実行時は読むだけ / D3・D4）。
"""

import json
import re
from functools import lru_cache
from pathlib import Path

# 配布名（canonical）→ トップレベル import 名 の内部マスタ（#477 / D3・D4）。
_ALIAS_MASTER_PATH = Path(__file__).parent.parent / "resources" / "pypi_import_aliases.json"

# 行頭（インデント可）の import 文。`import a.b`, `import a as b`, `from a.b import c` を拾う。
_IMPORT_RE = re.compile(
    r"^[ \t]*(?:import|from)[ \t]+([A-Za-z_][\w.]*)",
    re.MULTILINE,
)


@lru_cache(maxsize=1)
def _load_import_aliases() -> dict[str, frozenset[str]]:
    """canonical 配布名 → import 名集合 の内部マスタを読み込む（プロセス内 1 回）。"""
    raw = json.loads(_ALIAS_MASTER_PATH.read_text(encoding="utf-8"))
    return {
        canonical: frozenset(names)
        for canonical, names in raw.get("aliases", {}).items()
    }


def _top_level(module: str) -> str:
    """ドット区切りの先頭要素（トップレベルモジュール名）を小文字で返す。"""
    return module.split(".", 1)[0].lower()


class PythonImportScanner:
    extensions: tuple[str, ...] = (".py", ".pyi")
    ecosystem: str = "pypi"

    def scan(self, content: str) -> set[str]:
        return {_top_level(m) for m in _IMPORT_RE.findall(content)}

    def matches(self, canonical_name: str, imported: set[str]) -> bool:
        # pypi canonical は PEP 503 正規化済み（小文字・``-`` 区切り）。
        # import 名は区切りが ``_`` になるのが一般的なので変換して照合する。
        candidate = canonical_name.replace("-", "_").replace(".", "_").lower()
        if candidate in imported:
            return True
        # 機械変換で当たらない既知の乖離（PyYAML→yaml 等）を内部マスタで補正する（#477）。
        aliases = _load_import_aliases().get(canonical_name)
        return bool(aliases and (aliases & imported))
