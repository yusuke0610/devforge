"""IaC パーサのレジストリ（ADR-0016 D10）。

v1 は Terraform / OpenTofu（``.tf``）のみ登録する。CloudFormation / Pulumi 等の
Tier2 は ``_PARSERS`` に 1 行足すだけで差し込める（plugin 型）。
"""

import os

from ..types import InfraResourceDeclaration
from .base import InfraParser
from .terraform import TerraformParser

# 登録済みパーサインスタンス。
_PARSERS: tuple[InfraParser, ...] = (TerraformParser(),)

# 拡張子（先頭ドット付き・小文字）→ パーサ。
_BY_EXTENSION: dict[str, InfraParser] = {
    ext: parser for parser in _PARSERS for ext in parser.extensions
}

# リポジトリ内で探索対象とする IaC ファイルの拡張子集合（D9 探索の対象判定に使う）。
INFRA_EXTENSIONS: frozenset[str] = frozenset(_BY_EXTENSION)


def _extension_of(path: str) -> str:
    """パスの拡張子（先頭ドット付き・小文字）を返す。"""
    return os.path.splitext(path)[1].lower()


def parser_for_path(path: str) -> InfraParser | None:
    """パスの拡張子に対応する IaC パーサを返す（無ければ None）。"""
    return _BY_EXTENSION.get(_extension_of(path))


def parse_infra(path: str, content: str) -> list[InfraResourceDeclaration]:
    """パスの拡張子に対応するパーサで IaC ファイルを解析する。

    未対応の拡張子なら空リストを返す。
    """
    parser = parser_for_path(path)
    if parser is None:
        return []
    return parser.parse(content)
