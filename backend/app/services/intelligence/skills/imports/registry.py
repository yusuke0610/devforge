"""import スキャナのレジストリ（ADR-0016 D6 / verify）。

Tier1（v1 必須）の全 4 エコシステム（Go / Python / JS-TS / Rust）のスキャナを登録する。
manifest パーサ（``manifests/registry.py``）と同じ plugin 思想で、Tier2 追加時は
``_SCANNERS`` に 1 行足すだけで差し込める。
"""

from .base import ImportScanner
from .go import GoImportScanner
from .js_ts import JsTsImportScanner
from .python import PythonImportScanner
from .rust import RustImportScanner

# Tier1 のスキャナインスタンス。
_SCANNERS: tuple[ImportScanner, ...] = (
    GoImportScanner(),
    PythonImportScanner(),
    JsTsImportScanner(),
    RustImportScanner(),
)

# エコシステム → スキャナ。
_BY_ECOSYSTEM: dict[str, ImportScanner] = {s.ecosystem: s for s in _SCANNERS}

# 拡張子 → スキャナ（ソースファイルの振り分け用）。
_BY_EXTENSION: dict[str, ImportScanner] = {
    ext: scanner for scanner in _SCANNERS for ext in scanner.extensions
}

# verify で取得対象とするソース拡張子の集合。
SOURCE_EXTENSIONS: frozenset[str] = frozenset(_BY_EXTENSION)


def scanner_for_extension(path: str) -> ImportScanner | None:
    """ファイルパスの拡張子に対応するスキャナを返す（未対応なら None）。"""
    dot = path.rfind(".")
    if dot < 0:
        return None
    return _BY_EXTENSION.get(path[dot:].lower())


def scanner_for_ecosystem(ecosystem: str) -> ImportScanner | None:
    """エコシステム識別子に対応するスキャナを返す（未対応なら None）。"""
    return _BY_ECOSYSTEM.get(ecosystem)
