"""スキル推論基盤の値オブジェクト（ADR-0016）。

機械が埋める Layer 1-2 の中間表現。永続化（models/skill.py）や API スキーマとは独立した、
パイプライン内部のドメイン型。
"""

from dataclasses import dataclass

# 依存の種類（D7）。manifest 由来の宣言区分をそのまま保持する。
#   direct  : 本番直接依存
#   dev     : 開発依存（package.json devDependencies 等）。実績スキルには混ぜない
#   indirect: 推移的依存（go.mod の `// indirect` 等）。除外対象
#   peer    : peerDependencies
#   build   : build-system 依存（pyproject build-system.requires 等）
DEPENDENCY_KINDS = ("direct", "dev", "indirect", "peer", "build")

# Layer 1 スキルの種別（D2）。
SKILL_KIND_LANGUAGE = "language"
SKILL_KIND_PACKAGE = "package"


@dataclass(frozen=True)
class PackageDeclaration:
    """manifest が宣言する 1 依存（declare ステージの出力 / D7）。

    package ID はエコシステム内で一意 = canonical なので、辞書による正規化は行わない（D3）。
    """

    ecosystem: str  # npm / pypi / go / cargo
    name: str  # エコシステム内で一意な package ID
    dependency_kind: str  # DEPENDENCY_KINDS のいずれか
    version_spec: str | None = None  # バージョン制約（生文字列。解釈はしない）
    # D9(f): manifest の相対パス（例: backend/requirements.txt）。証跡用。直下なら "package.json" 等。
    source_path: str | None = None
