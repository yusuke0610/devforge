"""Python import スキャナ（ecosystem=pypi / D6）。

``import X`` / ``from X import ...`` のトップレベルモジュール名を抽出する。
pypi の package ID と import 名はしばしば異なる（PyYAML→yaml 等）が、辞書は持たず
``canonical_name`` の ``-``/``.``→``_`` 変換のみで照合する。差異は false negative として受容。
"""

import re

# 行頭（インデント可）の import 文。`import a.b`, `import a as b`, `from a.b import c` を拾う。
_IMPORT_RE = re.compile(
    r"^[ \t]*(?:import|from)[ \t]+([A-Za-z_][\w.]*)",
    re.MULTILINE,
)


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
        return candidate in imported
