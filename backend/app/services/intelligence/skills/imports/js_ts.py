"""JavaScript / TypeScript import スキャナ（ecosystem=npm / D6）。

``import ... from "spec"`` / ``import "spec"`` / ``require("spec")`` / ``import("spec")``
の module specifier を抽出し、相対 import（``.`` / ``..`` / ``/`` 始まり）を除外する。
specifier から package 名を取り出す（``@scope/name`` はスコープ込み、それ以外は先頭セグメント。
subpath import ``pkg/sub`` は ``pkg`` に丸める）。npm の package ID はそのまま canonical。
"""

import re

# from "x" / from 'x' / import "x" / require("x") / import("x") の引用符内を捕捉。
_SPEC_RE = re.compile(
    r"""(?:\bfrom|\bimport|\brequire)\s*\(?\s*["']([^"']+)["']""",
)

# コメント除去（誤検出抑制）。block コメント /* ... */ と行コメント // ... を落とす。
# 行コメントは URL（http://）を壊さないよう直前が ":" でない場合のみ除去する。
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT_RE = re.compile(r"(?<!:)//[^\n]*")


def _strip_comments(content: str) -> str:
    """import 走査前にコメントを除去する（コメント内の import/require 誤検出を防ぐ）。

    文字列リテラル内の import 風テキスト（``'import("x")'`` 等）までは除去しない。
    昇格のみ・実害は低 confidence の誤昇格に留まるため、残差は受容する（D6 / 保守的）。
    """
    return _LINE_COMMENT_RE.sub(" ", _BLOCK_COMMENT_RE.sub(" ", content))


def _package_of(spec: str) -> str | None:
    """module specifier から package 名を取り出す。相対 import は None。"""
    if not spec or spec.startswith((".", "/")):
        return None
    parts = spec.split("/")
    if spec.startswith("@"):
        # スコープ付き: @scope/name（最低 2 セグメント必要）
        if len(parts) < 2:
            return None
        return "/".join(parts[:2])
    return parts[0]


class JsTsImportScanner:
    extensions: tuple[str, ...] = (
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".mts",
        ".cts",
    )
    ecosystem: str = "npm"

    def scan(self, content: str) -> set[str]:
        names: set[str] = set()
        for spec in _SPEC_RE.findall(_strip_comments(content)):
            pkg = _package_of(spec)
            if pkg:
                names.add(pkg)
        return names

    def matches(self, canonical_name: str, imported: set[str]) -> bool:
        # npm の package ID（@scope/name 含む）はそのまま import される。
        return canonical_name in imported
