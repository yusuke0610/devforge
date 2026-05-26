"""
職務経歴書フォーマット用の共通ユーティリティ。

PDF（HTML 経由）と Markdown の両ジェネレータで重複していた
- 技術スタックカテゴリの日本語ラベル
- dict / ORM 両対応の属性アクセス
- プレゼンテーション非依存の入力正規化（旧スキーマ後方互換・スタックのカテゴリ別グルーピング）

を集約する。

注意:
- 期間表示の `format_period` は PDF（「YYYY 年 MM 月〜現在」）と Markdown（「YYYY-MM - 現在」）で
  意図的に出力フォーマットが異なる。共通化すると出力崩れが起きるためここには置かない。
- HTML エスケープと Markdown エスケープも別物のためここでは扱わない。
- ここに置くのは「表示形式に依存しない正規化」だけ。ラベル付けや HTML/Markdown 組み立ては
  各ジェネレータ側に残す（同じ正規化を両者で別々に持つと片方だけ乖離する事故を防ぐ）。
"""

from collections.abc import Iterable
from typing import Any

#: 技術スタックカテゴリの日本語ラベル。PDF / Markdown で共通利用する。
CATEGORY_LABELS: dict[str, str] = {
    "language": "言語",
    "framework": "FW",
    "os": "OS",
    "db": "DB",
    "cloud_provider": "クラウド",
    "container": "コンテナ",
    "iac": "IaC",
    "vcs": "バージョン管理",
    "ci_cd": "CI/CD",
    "project_tool": "プロジェクトツール",
    "monitoring": "監視・可観測性",
    "middleware": "ミドルウェア",
    "ai_agent": "AIエージェント",
}


def attr(obj: Any, key: str, default: Any = "") -> Any:
    """dict / ORM オブジェクト両対応の属性アクセスヘルパ。"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def normalize_clients(experience: Any) -> list[Any]:
    """職歴から取引先（clients）リストを取り出す（dict / ORM 両対応）。

    旧スキーマ後方互換: ``clients`` が無く ``projects`` だけがある場合は、
    無名取引先 1 件（``{"name": "", "projects": [...]}``）に畳んで返す。
    """
    clients = attr(experience, "clients", [])
    if not clients and attr(experience, "projects", None):
        clients = [{"name": "", "projects": attr(experience, "projects", [])}]
    return clients


def normalize_team(project: Any) -> Any | None:
    """プロジェクトから体制（team）情報を取り出す（dict / ORM 両対応）。

    旧スキーマ後方互換: ``team`` が無く ``scale`` だけがある場合は
    ``{"total": scale, "members": []}`` に変換して返す。
    team も scale も無ければ ``None`` を返す。
    """
    team = attr(project, "team", None)
    if not team and attr(project, "scale", None):
        team = {"total": attr(project, "scale"), "members": []}
    return team


def group_stacks_by_category(stacks: Iterable[Any]) -> dict[str, list[str]]:
    """technology_stacks を ``{category: [name, ...]}`` にグルーピングする（dict / ORM 両対応）。

    最初に出現した category の順序を保持する。表示用ラベル付けは呼び出し側が行う。
    """
    grouped: dict[str, list[str]] = {}
    for st in stacks:
        grouped.setdefault(attr(st, "category"), []).append(attr(st, "name"))
    return grouped
