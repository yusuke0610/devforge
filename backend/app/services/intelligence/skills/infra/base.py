"""IaC パーサのプラグイン基底（ADR-0016 D10）。

各 IaC ツールのパーサは ``InfraParser`` を実装し、``extensions``（対応するファイル拡張子）と
``parse``（ファイル内容 → ``InfraResourceDeclaration`` 列）だけを提供する。新しい IaC ツール
（CloudFormation / Pulumi 等）は ``registry.py`` に 1 行足すだけで差し込める（plugin 型）。

manifest パーサ（``manifests/base.py``）との違い:
  - manifest は basename（``go.mod`` 等）で一致、IaC は拡張子（``.tf``）で一致する。
  - 出力型が ``PackageDeclaration`` ではなく ``InfraResourceDeclaration``（provider / resource 粒度）。

パーサは I/O を行わない純粋関数として実装する（ファイル取得は呼び出し側の責務）。
壊れた IaC ファイルは例外を投げずベストエフォート（取れた分だけ返す）で処理する
（1 リポの解析失敗で連携全体を落とさない）。
"""

from typing import Protocol, runtime_checkable

from ..types import InfraResourceDeclaration


@runtime_checkable
class InfraParser(Protocol):
    """IaC パーサのインターフェース。"""

    # このパーサが対応するファイル拡張子（先頭ドット付き。例: (".tf",)）。
    extensions: tuple[str, ...]
    # IaC ツール識別子（"terraform"）。
    tool: str

    def parse(self, content: str) -> list[InfraResourceDeclaration]:
        """IaC ファイルの内容を ``InfraResourceDeclaration`` 列へ変換する。"""
        ...
