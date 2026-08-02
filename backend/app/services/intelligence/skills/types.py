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

# 「本番で直接使うと決めた依存」。実績スキルの採用基準（aggregator）と、リポジトリの
# 依存の厚み（ADR-0026 決定 4 の選定シグナル）が同じ意味で参照するため定数化する。
DEPENDENCY_KIND_DIRECT = "direct"

# Layer 1 スキルの種別（D2）。
SKILL_KIND_LANGUAGE = "language"
SKILL_KIND_PACKAGE = "package"
# IaC（Terraform 等）から検出するインフラリソースのスキル種別（D10）。
# language（幅）/ package（依存）とは検出方法が異なるため別 kind とする。
SKILL_KIND_INFRA = "infra"


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


@dataclass(frozen=True)
class InfraResourceDeclaration:
    """IaC が宣言する 1 インフラリソース（declare 相当の出力 / D10）。

    Terraform 等の HCL から抽出する。provider（クラウド事業者）と resource_type
    （具体サービス。例 ``aws_s3_bucket``）を保持する。canonical は raw type をそのまま
    使い（辞書を持たない / D3）、表示名への畳み込みは後段の human-in-the-loop に委ねる（D8）。
    """

    tool: str  # IaC ツール（"terraform"）。将来の Pulumi / CloudFormation と区別する
    provider: str  # クラウドプロバイダ（"aws" / "google" / "cloudflare" 等）
    # 具体サービスの raw な resource type（"aws_s3_bucket"）。provider 宣言のみなら None
    resource_type: str | None = None
    # D9(f): 検出した .tf の相対パス（例: infra/modules/vpc/main.tf）。証跡用
    source_path: str | None = None
