"""repo_analyzer モジュールのユニットテスト。"""

from app.services.intelligence.github.repo_analyzer import compute_language_ratios

# ── 言語 ratio 算出テスト ────────────────────────────────────────────────


def test_compute_language_ratios_basic() -> None:
    """言語バイト数から比率が正しく算出されること。"""
    languages = {"Python": 80, "JavaScript": 20}
    ratios = compute_language_ratios(languages)
    assert abs(ratios["Python"] - 0.8) < 1e-9
    assert abs(ratios["JavaScript"] - 0.2) < 1e-9


def test_compute_language_ratios_single() -> None:
    """1言語のみの場合は比率が 1.0 となること。"""
    ratios = compute_language_ratios({"Python": 100})
    assert ratios["Python"] == 1.0


def test_compute_language_ratios_zero_guard() -> None:
    """合計バイト数が 0 の場合は空の辞書を返すこと（0除算ガード）。"""
    ratios = compute_language_ratios({})
    assert ratios == {}


def test_compute_language_ratios_all_zero_bytes() -> None:
    """全言語のバイト数が 0 の場合も空の辞書を返すこと。"""
    ratios = compute_language_ratios({"Python": 0, "Go": 0})
    assert ratios == {}
