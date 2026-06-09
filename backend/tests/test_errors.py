"""``app.core.errors`` のエラーコード推定ロジックの回帰テスト。

``infer_error_code`` は status_code と detail（dict / str / None）から ErrorCode を
引く分岐の多い純粋関数で、FE へ返すエラーコード契約の要。特に
"GitHubユーザーが見つかりません" の部分文字列マッチは messages.json の文言変更で
無言の劣化（INTERNAL_ERROR へ fallback）を起こしうるため、結合を明示的に固定する。
"""

import pytest
from app.core.errors import (
    ErrorCode,
    infer_async_error_code,
    infer_error_code,
    resolve_async_error_code,
)
from app.core.messages import get_error


@pytest.mark.parametrize(
    ("status_code", "detail", "expected"),
    [
        # dict + 有効な code 文字列 → その code をそのまま採用（status_code より優先）
        (500, {"code": "RATE_LIMITED", "message": "x"}, ErrorCode.RATE_LIMITED),
        # dict + 無効な code 文字列 → code を無視して message / status へ fall through
        (404, {"code": "NOT_A_REAL_CODE"}, ErrorCode.VALIDATION_ERROR),
        # dict + message のみ（code なし）→ message と status で判定
        (500, {"message": "なにかのエラー"}, ErrorCode.INTERNAL_ERROR),
        # str detail → そのまま message として扱う
        (401, "認証が必要です", ErrorCode.AUTH_REQUIRED),
        # detail なし → status_code のみで判定
        (429, None, ErrorCode.RATE_LIMITED),
        # GitHub ユーザー未検出の部分文字列は status より優先
        (500, "GitHubユーザーが見つかりません: foo", ErrorCode.GITHUB_USER_NOT_FOUND),
        (200, "GitHubユーザーが見つかりません: foo", ErrorCode.GITHUB_USER_NOT_FOUND),
        # status_code マッピング
        (401, None, ErrorCode.AUTH_REQUIRED),
        (429, None, ErrorCode.RATE_LIMITED),
        (400, None, ErrorCode.VALIDATION_ERROR),
        (404, None, ErrorCode.VALIDATION_ERROR),
        (409, None, ErrorCode.VALIDATION_ERROR),
        (422, None, ErrorCode.VALIDATION_ERROR),
        # マッピングに無い status → INTERNAL_ERROR
        (500, None, ErrorCode.INTERNAL_ERROR),
        (418, None, ErrorCode.INTERNAL_ERROR),
    ],
)
def test_infer_error_code(status_code: int, detail, expected: ErrorCode) -> None:
    """status_code と detail の各組み合わせで期待する ErrorCode を返すこと。"""
    assert infer_error_code(status_code, detail) is expected


def test_infer_error_code_dict_code_takes_precedence_over_github_message() -> None:
    """dict の有効な code は GitHub 部分文字列マッチより優先されること。"""
    detail = {"code": "VALIDATION_ERROR", "message": "GitHubユーザーが見つかりません: foo"}
    assert infer_error_code(500, detail) is ErrorCode.VALIDATION_ERROR


def test_github_user_not_found_message_keeps_substring_contract() -> None:
    """messages.json の実際の文言が GitHub 未検出の部分文字列契約を満たすこと。

    ``infer_error_code`` がキーにしている "GitHubユーザーが見つかりません" を
    messages.json 側の文言変更で取りこぼすと、FE で GITHUB_USER_NOT_FOUND の
    リカバリ表示が出なくなる。文言が変わったら本テストで検知する。
    """
    message = get_error("github_link.github_user_not_found", username="someone")
    assert infer_error_code(500, message) is ErrorCode.GITHUB_USER_NOT_FOUND


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (None, None),
        ("", None),
        ("GitHubユーザーが見つかりません: foo", ErrorCode.GITHUB_USER_NOT_FOUND),
        ("不明なエラー", ErrorCode.INTERNAL_ERROR),
    ],
)
def test_infer_async_error_code(message, expected) -> None:
    """非同期タスクのエラーメッセージから ErrorCode を引く（空は None）。"""
    assert infer_async_error_code(message) is expected


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (None, None),
        ("", None),
        ("GitHubユーザーが見つかりません: foo", "GITHUB_USER_NOT_FOUND"),
        ("不明なエラー", "INTERNAL_ERROR"),
    ],
)
def test_resolve_async_error_code(message, expected) -> None:
    """``resolve_async_error_code`` は code の文字列値（または None）を返すこと。"""
    assert resolve_async_error_code(message) == expected
