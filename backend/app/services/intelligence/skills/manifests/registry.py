"""manifest パーサのレジストリ（ADR-0016 D7）。

Tier1（v1 必須）のパーサだけを登録する。Tier2（Java-Kotlin / Ruby / PHP）は
``_PARSERS`` に 1 行足すだけで差し込める（plugin 型）。
"""

from ..types import PackageDeclaration
from .base import ManifestParser
from .cargo_toml import CargoTomlParser
from .go_mod import GoModParser
from .package_json import PackageJsonParser
from .pyproject import PyprojectParser
from .requirements_txt import RequirementsTxtParser

# Tier1 のパーサインスタンス。
_PARSERS: tuple[ManifestParser, ...] = (
    GoModParser(),
    PyprojectParser(),
    RequirementsTxtParser(),
    PackageJsonParser(),
    CargoTomlParser(),
)

# ファイル名 → パーサ。取得すべき manifest ファイル名の判定にも使う。
_BY_FILENAME: dict[str, ManifestParser] = {
    filename: parser for parser in _PARSERS for filename in parser.filenames
}

# リポジトリ直下で取得を試みる manifest ファイル名（D7: v1 は直下のみ）。
MANIFEST_FILENAMES: frozenset[str] = frozenset(_BY_FILENAME)


def parse_manifest(filename: str, content: str) -> list[PackageDeclaration]:
    """ファイル名に対応するパーサで manifest を解析する。

    未対応のファイル名なら空リストを返す。
    """
    parser = _BY_FILENAME.get(filename)
    if parser is None:
        return []
    return parser.parse(content)
