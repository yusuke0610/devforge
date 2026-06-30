"""import 解析（verify ステージ / ADR-0016 D6）。

宣言された direct 依存が実際に import されているかをソースから判定し、``manifest_declared``
を ``actual_import`` へ昇格させる素を作る。辞書は持たず、エコシステム別の機械的規則のみで
照合する（取りこぼしは false negative として受容）。
"""

from .base import ImportScanner
from .registry import (
    SOURCE_EXTENSIONS,
    scanner_for_ecosystem,
    scanner_for_extension,
)

__all__ = [
    "ImportScanner",
    "SOURCE_EXTENSIONS",
    "scanner_for_ecosystem",
    "scanner_for_extension",
]
