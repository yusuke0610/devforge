"""manifest パーサのプラグイン基底（ADR-0016 D7）。

各エコシステムのパーサは ``ManifestParser`` を実装し、``filenames``（対応する manifest の
ファイル名）と ``parse``（ファイル内容 → ``PackageDeclaration`` 列）だけを提供する。
新しいエコシステムは ``registry.py`` に 1 行足すだけで差し込める。

パーサは I/O を行わない純粋関数として実装する（ファイル取得は呼び出し側の責務）。
壊れた manifest は例外を投げず空リストを返す（1 リポの解析失敗で連携全体を落とさない）。
"""

from typing import Protocol, runtime_checkable

from ..types import PackageDeclaration


@runtime_checkable
class ManifestParser(Protocol):
    """manifest パーサのインターフェース。"""

    # このパーサが対応する manifest のファイル名（リポジトリ直下からの相対）。
    filenames: tuple[str, ...]
    # エコシステム識別子（npm / pypi / go / cargo）。
    ecosystem: str

    def parse(self, content: str) -> list[PackageDeclaration]:
        """manifest の内容を ``PackageDeclaration`` 列へ変換する。"""
        ...
