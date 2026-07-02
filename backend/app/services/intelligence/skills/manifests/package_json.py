"""package.json パーサ（ecosystem=npm / D7）。

宣言ブロックごとに dependency_kind を割り当てる:
  dependencies → direct / devDependencies → dev /
  peerDependencies → peer / optionalDependencies → direct
devDependencies は実績スキルに混ぜない素になる（D7）。
"""

import json

from ..types import PackageDeclaration

_BLOCK_KINDS = {
    "dependencies": "direct",
    "devDependencies": "dev",
    "peerDependencies": "peer",
    "optionalDependencies": "direct",
}


class PackageJsonParser:
    filenames: tuple[str, ...] = ("package.json",)
    ecosystem: str = "npm"

    def parse(self, content: str) -> list[PackageDeclaration]:
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return []
        if not isinstance(data, dict):
            return []

        declarations: list[PackageDeclaration] = []
        for block, kind in _BLOCK_KINDS.items():
            deps = data.get(block)
            if not isinstance(deps, dict):
                continue
            for name, version in deps.items():
                if not name:
                    continue
                declarations.append(
                    PackageDeclaration(
                        ecosystem=self.ecosystem,
                        name=name,
                        dependency_kind=kind,
                        version_spec=version if isinstance(version, str) else None,
                    )
                )
        return declarations
