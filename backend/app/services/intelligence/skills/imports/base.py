"""import スキャナのプラグイン基底（ADR-0016 D6 / verify ステージ）。

各エコシステムのスキャナは ``ImportScanner`` を実装し、ソースファイル内容から
「import された名前/パス」の集合を抽出する（``scan``）。宣言された package が実際に
import されているかの判定（``matches``）もエコシステム依存なのでスキャナに集約する
（npm は完全一致、go は接頭辞一致、pypi/cargo は ``-``→``_`` 変換後の一致など）。

辞書は持たない（D3）。package ID → import 名の変換は機械的な規則のみで行い、取りこぼし
（例: PyYAML→yaml）は **昇格漏れ（false negative）として受容**する。verify は declare の
証跡を昇格させるだけで降格はしないため、未検出でも declare 証跡はそのまま残る（D8）。

スキャナは I/O を行わない純粋関数として実装する（ファイル取得は呼び出し側の責務）。
壊れたソースでも例外を投げず空集合を返す（1 ファイルの解析失敗で連携全体を落とさない）。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ImportScanner(Protocol):
    """import スキャナのインターフェース。"""

    # このスキャナが対応するソースファイルの拡張子（".py" 等。先頭ドット込み）。
    extensions: tuple[str, ...]
    # エコシステム識別子（npm / pypi / go / cargo）。manifest 側の ecosystem と一致させる。
    ecosystem: str

    def scan(self, content: str) -> set[str]:
        """ソース内容から import された名前/パスの集合を抽出する。"""
        ...

    def matches(self, canonical_name: str, imported: set[str]) -> bool:
        """宣言 package（canonical 名）が ``imported`` 内で実使用されているか判定する。"""
        ...
