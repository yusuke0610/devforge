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
    """
    Access a value from a mapping or an attribute from an object using a single call.
    
    If `obj` is a dict-like mapping, returns `obj.get(key, default)`; otherwise returns `getattr(obj, key, default)`.
    
    Parameters:
        obj (Any): A mapping (e.g., dict) or an object with attributes.
        key (str): The key or attribute name to retrieve.
        default (Any): Value returned when the key/attribute is missing (defaults to empty string).
    
    Returns:
        Any: The retrieved value if present, otherwise `default`.
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def normalize_clients(experience: Any) -> list[Any]:
    """
    Extract the list of clients from an experience object, supporting both dict and ORM-style access.
    
    If the experience has no `clients` but has `projects`, returns a single unnamed client `{"name": "", "projects": [...]}` for backward compatibility with the old schema.
    
    Returns:
        list[Any]: A list of client objects (possibly a single synthesized unnamed client).
    """
    clients = attr(experience, "clients", [])
    if not clients and attr(experience, "projects", None):
        clients = [{"name": "", "projects": attr(experience, "projects", [])}]
    return clients


def normalize_team(project: Any) -> Any | None:
    """
    Extract team information from a project object, supporting both dict and attribute-style access.
    
    If `team` is missing but `scale` exists, a compatible team object `{"total": scale, "members": []}` is returned. If neither `team` nor `scale` is present, `None` is returned.
    
    Returns:
        dict | None: A team object with keys `"total"` (number) and `"members"` (list) when available, otherwise `None`.
    """
    team = attr(project, "team", None)
    if not team and attr(project, "scale", None):
        team = {"total": attr(project, "scale"), "members": []}
    return team


def group_stacks_by_category(stacks: Iterable[Any]) -> dict[str, list[str]]:
    """
    Group technology stack entries into a mapping from category to a list of names.
    
    Preserves the order in which categories first appear; display labeling is the caller's responsibility.
    
    Returns:
        dict[str, list[str]]: Mapping from each category to a list of stack names. Categories appear in insertion order (first-seen first).
    """
    grouped: dict[str, list[str]] = {}
    for st in stacks:
        grouped.setdefault(attr(st, "category"), []).append(attr(st, "name"))
    return grouped
