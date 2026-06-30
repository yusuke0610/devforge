"""pyproject.toml パーサ（ecosystem=pypi / D7）。

PEP 621（[project]）と Poetry（[tool.poetry]）の双方を読む:
  - [project].dependencies → direct
  - [project.optional-dependencies].<group> → dev（dev/test/lint/docs/typing 系）/ それ以外は direct
  - [build-system].requires → build
  - [tool.poetry.dependencies] → direct（python 行は除外）
  - [tool.poetry.group.<g>.dependencies] / [tool.poetry.dev-dependencies] → dev/direct（group 名で判定）
"""

import tomllib

from ..types import PackageDeclaration
from ._pep508 import extract_package_name

# 開発系とみなす extras / poetry group 名（→ dependency_kind="dev"）。
_DEV_GROUP_NAMES = frozenset({"dev", "test", "tests", "lint", "docs", "typing", "ci"})


class PyprojectParser:
    filenames: tuple[str, ...] = ("pyproject.toml",)
    ecosystem: str = "pypi"

    def parse(self, content: str) -> list[PackageDeclaration]:
        try:
            data = tomllib.loads(content)
        except (tomllib.TOMLDecodeError, ValueError):
            return []

        declarations: list[PackageDeclaration] = []
        self._parse_pep621(declarations, data)
        self._parse_build_system(declarations, data)
        self._parse_poetry(declarations, data)
        return declarations

    def _add(self, out: list[PackageDeclaration], raw_name: str, kind: str) -> None:
        name = extract_package_name(raw_name)
        if not name:
            return
        out.append(
            PackageDeclaration(
                ecosystem=self.ecosystem, name=name, dependency_kind=kind, version_spec=None
            )
        )

    def _parse_pep621(self, out: list[PackageDeclaration], data: dict) -> None:
        project = data.get("project")
        if not isinstance(project, dict):
            return
        for spec in project.get("dependencies") or []:
            if isinstance(spec, str):
                self._add(out, spec, "direct")
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group, specs in optional.items():
                kind = "dev" if group.lower() in _DEV_GROUP_NAMES else "direct"
                for spec in specs or []:
                    if isinstance(spec, str):
                        self._add(out, spec, kind)

    def _parse_build_system(self, out: list[PackageDeclaration], data: dict) -> None:
        build_system = data.get("build-system")
        if not isinstance(build_system, dict):
            return
        for spec in build_system.get("requires") or []:
            if isinstance(spec, str):
                self._add(out, spec, "build")

    def _parse_poetry(self, out: list[PackageDeclaration], data: dict) -> None:
        poetry = (data.get("tool") or {}).get("poetry")
        if not isinstance(poetry, dict):
            return
        for name in (poetry.get("dependencies") or {}):
            if name.lower() != "python":
                self._add(out, name, "direct")
        # 旧形式 [tool.poetry.dev-dependencies]
        for name in (poetry.get("dev-dependencies") or {}):
            self._add(out, name, "dev")
        # 新形式 [tool.poetry.group.<g>.dependencies]
        groups = poetry.get("group")
        if isinstance(groups, dict):
            for group_name, group in groups.items():
                if not isinstance(group, dict):
                    continue
                kind = "dev" if group_name.lower() in _DEV_GROUP_NAMES else "direct"
                for name in (group.get("dependencies") or {}):
                    self._add(out, name, kind)
