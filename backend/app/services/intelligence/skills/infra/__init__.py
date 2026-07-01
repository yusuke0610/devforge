"""IaC からのインフラリソース検出（ADR-0016 D10）。

Terraform 等の HCL を解析し、provider（クラウド事業者）と resource（具体サービス）の
宣言を ``InfraResourceDeclaration`` として抽出する。plugin 型パーサ（``manifests`` /
``imports`` と同構造）で、対応 IaC ツールは ``registry.py`` で差し込む。
"""

from ..types import InfraResourceDeclaration
from .base import InfraParser
from .registry import (
    INFRA_EXTENSIONS,
    parse_infra,
    parser_for_path,
)

__all__ = [
    "INFRA_EXTENSIONS",
    "InfraParser",
    "InfraResourceDeclaration",
    "parse_infra",
    "parser_for_path",
]
