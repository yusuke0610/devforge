"""go.mod パーサ（ecosystem=go / D7）。

``require`` の単行・ブロック両形式を読む。``// indirect`` 付きは推移的依存として
``dependency_kind="indirect"`` を立てる（実績スキルからは除外する素になる）。
"""

import re

from ..types import PackageDeclaration

# `require module/path v1.2.3` または ブロック内行 `module/path v1.2.3 // indirect`
_REQUIRE_LINE = re.compile(
    r"^(?P<path>[^\s()]+)\s+(?P<version>v[^\s]+)(?P<comment>\s+//.*)?$"
)


class GoModParser:
    filenames = ("go.mod",)
    ecosystem = "go"

    def parse(self, content: str) -> list[PackageDeclaration]:
        declarations: list[PackageDeclaration] = []
        in_block = False
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("//"):
                continue

            if in_block:
                if line.startswith(")"):
                    in_block = False
                    continue
                self._append(declarations, line)
                continue

            if line.startswith("require ("):
                in_block = True
                continue
            if line.startswith("require "):
                self._append(declarations, line[len("require "):].strip())
        return declarations

    def _append(self, out: list[PackageDeclaration], line: str) -> None:
        match = _REQUIRE_LINE.match(line)
        if not match:
            return
        is_indirect = match.group("comment") and "indirect" in match.group("comment")
        out.append(
            PackageDeclaration(
                ecosystem=self.ecosystem,
                name=match.group("path"),
                dependency_kind="indirect" if is_indirect else "direct",
                version_spec=match.group("version"),
            )
        )
