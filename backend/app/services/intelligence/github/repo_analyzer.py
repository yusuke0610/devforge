"""
リポジトリ解析モジュール。

言語 ratio 算出などの純粋関数を提供する。
"""

from typing import Dict


def compute_language_ratios(languages: Dict[str, int]) -> Dict[str, float]:
    """
    言語バイト数から各言語の比率を算出する。

    0除算ガード付き。合計バイト数が0の場合は空の辞書を返す。
    """
    total = sum(languages.values())
    if total == 0:
        return {}
    return {lang: count / total for lang, count in languages.items()}
