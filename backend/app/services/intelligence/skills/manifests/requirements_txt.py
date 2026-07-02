"""requirements.txt パーサ（ecosystem=pypi / D7）。

1 行 1 依存。コメント・オプション行（-r / -e / --flag）・URL 直指定はスキップする。
requirements.txt は dev/direct を区別しないため全て direct 扱い（dev 変種の取り込みは後続）。
"""

from ..types import PackageDeclaration
from ._pep508 import extract_package_name


class RequirementsTxtParser:
    filenames: tuple[str, ...] = ("requirements.txt",)
    ecosystem: str = "pypi"

    def parse(self, content: str) -> list[PackageDeclaration]:
        declarations: list[PackageDeclaration] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # 環境マーカー（; python_version<...）の前で切る。
            spec = line.split(";", 1)[0].strip()
            name = extract_package_name(spec)
            if not name:
                continue
            declarations.append(
                PackageDeclaration(
                    ecosystem=self.ecosystem,
                    name=name,
                    dependency_kind="direct",
                    version_spec=None,
                )
            )
        return declarations
