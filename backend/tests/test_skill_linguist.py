"""Linguist 言語リゾルバのテスト（ADR-0016 discover / D3・D4）。"""

from app.services.intelligence.skills.linguist import resolve_language


def test_canonical_language() -> None:
    resolved = resolve_language("Python")
    assert resolved is not None
    assert resolved.canonical == "Python"
    assert resolved.display == "Python"


def test_alias_is_normalized() -> None:
    """エイリアスが正規名へ名寄せされること。"""
    resolved = resolve_language("golang")
    assert resolved is not None
    assert resolved.canonical == "Go"


def test_display_correction_for_data_language() -> None:
    """keep_data の data 言語は表示名補正付きで残ること（HCL → Terraform）。"""
    hcl = resolve_language("HCL")
    assert hcl is not None
    assert hcl.canonical == "HCL"
    assert hcl.display == "Terraform"

    docker = resolve_language("Dockerfile")
    assert docker is not None
    assert docker.display == "Docker"


def test_kept_data_language_sql() -> None:
    """keep_data に挙げた SQL は除外されないこと。"""
    assert resolve_language("SQL") is not None


def test_excluded_markup_is_dropped() -> None:
    """明示除外（HTML/CSS/YAML）は None を返すこと。"""
    assert resolve_language("HTML") is None
    assert resolve_language("CSS") is None
    assert resolve_language("YAML") is None


def test_unknown_language_falls_back_to_included() -> None:
    """マスタ未収録かつ非除外の言語は programming とみなして採用されること。"""
    # 将来 master に収録され得る実在名ではなく、確実に未収録の合成トークンを使う。
    unknown = "__CR_UNLISTED_LANGUAGE__"
    resolved = resolve_language(unknown)
    assert resolved is not None
    assert resolved.canonical == unknown
    assert resolved.display == unknown
    assert resolved.parent is None


def test_empty_name_returns_none() -> None:
    assert resolve_language("") is None
