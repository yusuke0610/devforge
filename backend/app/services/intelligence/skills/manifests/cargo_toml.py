"""Cargo.toml パーサ（ecosystem=cargo / D7）。

[dependencies] → direct / [dev-dependencies] → dev / [build-dependencies] → build。
依存値は文字列（バージョン）または table（version/git/path 等）の両方を許容する。
"""

import tomllib

from ..types import PackageDeclaration

_SECTION_KINDS = {
    "dependencies": "direct",
    "dev-dependencies": "dev",
    "build-dependencies": "build",
}


class CargoTomlParser:
    filenames = ("Cargo.toml",)
    ecosystem = "cargo"

    def parse(self, content: str) -> list[PackageDeclaration]:
        try:
            data = tomllib.loads(content)
        except (tomllib.TOMLDecodeError, ValueError):
            return []

        declarations: list[PackageDeclaration] = []
        for section, kind in _SECTION_KINDS.items():
            self._collect(declarations, data.get(section), kind)
        # [target.<cfg>.dependencies] も拾う（プラットフォーム別依存）。
        target = data.get("target")
        if isinstance(target, dict):
            for cfg in target.values():
                if isinstance(cfg, dict):
                    self._collect(declarations, cfg.get("dependencies"), "direct")
        return declarations

    def _collect(self, out: list[PackageDeclaration], section, kind: str) -> None:
        if not isinstance(section, dict):
            return
        for name, spec in section.items():
            if not name:
                continue
            version = spec if isinstance(spec, str) else None
            if version is None and isinstance(spec, dict):
                version = spec.get("version")
            out.append(
                PackageDeclaration(
                    ecosystem=self.ecosystem,
                    name=name,
                    dependency_kind=kind,
                    version_spec=version if isinstance(version, str) else None,
                )
            )
