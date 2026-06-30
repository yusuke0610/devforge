"""Rust import スキャナ（ecosystem=cargo / D6）。

``use crate_name::...`` と ``extern crate crate_name;`` の先頭クレート名を抽出する。
Cargo の crate 名は ``-`` を含みうるが、ソースでは ``_`` に変換されて使われるため
（serde-json → ``use serde_json``）、canonical 名も ``-``→``_`` 変換して照合する。
``crate`` / ``self`` / ``super`` / ``std`` / ``core`` / ``alloc`` は外部クレートでないため除外。
"""

import re

# 先頭の可視性修飾子（pub / pub(crate) / pub(in path) 等）を任意で許容し、
# `pub use serde::...` のような re-export も外部クレート使用として拾う。
_USE_RE = re.compile(
    r"^[ \t]*(?:pub(?:\([^)]*\))?[ \t]+)?use[ \t]+([A-Za-z_]\w*)", re.MULTILINE
)
_EXTERN_RE = re.compile(r"^[ \t]*extern[ \t]+crate[ \t]+([A-Za-z_]\w*)", re.MULTILINE)

# 外部クレートでない予約パスセグメント。
_NON_CRATE = frozenset({"crate", "self", "super", "std", "core", "alloc"})


class RustImportScanner:
    extensions = (".rs",)
    ecosystem = "cargo"

    def scan(self, content: str) -> set[str]:
        names = set(_USE_RE.findall(content)) | set(_EXTERN_RE.findall(content))
        return {n for n in names if n not in _NON_CRATE}

    def matches(self, canonical_name: str, imported: set[str]) -> bool:
        candidate = canonical_name.replace("-", "_")
        return candidate in imported
