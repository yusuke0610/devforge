"""BE の ``ErrorCode`` enum と FE の ``ERROR_CODES`` の集合一致を検証するテスト。

エラーコードは OpenAPI のスキーマに enum 値として乗らないため codegen で同期できず、
``backend/app/core/errors.py:ErrorCode``（正本）と
``web/src/constants/errorCodes.ts:ERROR_CODES`` を手動同期している。
片方だけ追加・削除すると FE で未知コードが ``INTERNAL_ERROR`` にサイレント fallback して
適切なメッセージ・recovery action が出なくなるため、ズレを CI で検知する。
"""

import re
from pathlib import Path

from app.core.errors import ErrorCode

# errorCodes.ts のリポジトリルートからの相対パス（monorepo 前提で frontend が隣接する）
_ERROR_CODES_TS_RELATIVE = Path("web") / "src" / "constants" / "errorCodes.ts"


def _locate_error_codes_ts() -> Path:
    """祖先ディレクトリを遡って FE の ``errorCodes.ts`` を探す。

    mutmut がテストを ``backend/mutants/tests/`` へコピーして実行する際は
    本ファイルの深さが 1 段増えるため、固定段数の ``parents[N]`` では
    リポジトリルートを特定できない（ADR-0017）。
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        target = candidate / _ERROR_CODES_TS_RELATIVE
        if target.exists():
            return target
    raise FileNotFoundError(
        f"FE のエラーコード定義が祖先ディレクトリに見つからない: {_ERROR_CODES_TS_RELATIVE}"
    )

# `export const ERROR_CODES = [ ... ] as const;` のブロックを取り出す
_ARRAY_BLOCK = re.compile(r"ERROR_CODES\s*=\s*\[(.*?)\]\s*as\s+const", re.DOTALL)
# ブロック内の "FOO_BAR" 形式の文字列リテラル
_CODE_LITERAL = re.compile(r'"([A-Z_]+)"')


def _parse_frontend_error_codes() -> set[str]:
    """FE の ``errorCodes.ts`` から ``ERROR_CODES`` の値集合を抽出する。"""
    source = _locate_error_codes_ts().read_text(encoding="utf-8")
    match = _ARRAY_BLOCK.search(source)
    assert match is not None, (
        "errorCodes.ts に `ERROR_CODES = [...] as const` ブロックが見つからない"
        "（定義形式が変わった場合は本テストのパーサも更新すること）"
    )
    return set(_CODE_LITERAL.findall(match.group(1)))


def test_error_codes_match_backend_enum() -> None:
    """BE ``ErrorCode`` と FE ``ERROR_CODES`` の値集合が完全一致すること。"""
    backend_codes = {code.value for code in ErrorCode}
    frontend_codes = _parse_frontend_error_codes()

    missing_in_frontend = backend_codes - frontend_codes
    extra_in_frontend = frontend_codes - backend_codes

    assert not missing_in_frontend, (
        "BE に存在するが FE 未定義のエラーコード（errorCodes.ts / errorMessages.ts へ追加が必要）: "
        f"{sorted(missing_in_frontend)}"
    )
    assert not extra_in_frontend, (
        "FE に存在するが BE 未定義のエラーコード（errors.py へ追加、または FE から削除が必要）: "
        f"{sorted(extra_in_frontend)}"
    )
