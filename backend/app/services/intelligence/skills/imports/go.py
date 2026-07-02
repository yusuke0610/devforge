"""Go import スキャナ（ecosystem=go / D6）。

単行 ``import "path"`` と ``import ( ... )`` ブロック内の引用符付きパスを抽出する
（エイリアス ``import x "path"`` / ドット import も引用符内を拾えば足りる）。
go.mod の module path に対し、import パスが完全一致または ``module/...`` の接頭辞一致なら
実使用とみなす（サブパッケージ import を許容）。
"""

import re

# 引用符付き import パス（ブロック内行・単行の両方をカバー）。
_IMPORT_LINE_RE = re.compile(r'^[ \t]*(?:[\w.]+[ \t]+)?"([^"]+)"', re.MULTILINE)
# import ブロック全体（import ( ... )）。
_IMPORT_BLOCK_RE = re.compile(r"import\s*\((.*?)\)", re.DOTALL)
# 単行 import "path"。
_IMPORT_SINGLE_RE = re.compile(r'^[ \t]*import[ \t]+(?:[\w.]+[ \t]+)?"([^"]+)"', re.MULTILINE)


class GoImportScanner:
    extensions: tuple[str, ...] = (".go",)
    ecosystem: str = "go"

    def scan(self, content: str) -> set[str]:
        paths: set[str] = set()
        for block in _IMPORT_BLOCK_RE.findall(content):
            paths.update(_IMPORT_LINE_RE.findall(block))
        paths.update(_IMPORT_SINGLE_RE.findall(content))
        return paths

    def matches(self, canonical_name: str, imported: set[str]) -> bool:
        # module path 完全一致 or サブパッケージ（module/...）の接頭辞一致。
        prefix = canonical_name + "/"
        return any(p == canonical_name or p.startswith(prefix) for p in imported)
