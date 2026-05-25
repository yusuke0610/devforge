from enum import Enum
from typing import Any, NoReturn
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict


class ErrorCode(str, Enum):
    """API エラーレスポンスの共通エラーコード。

    本 enum は FE 側の ``frontend/src/constants/errorCodes.ts:ERROR_CODES`` および
    ``frontend/src/constants/errorMessages.ts:ERROR_CONFIG`` のキー集合と一致させること。
    片方だけ変更すると FE 側で ``INTERNAL_ERROR`` にサイレント fallback して
    適切なメッセージと recovery action が表示されなくなる。

    新しいコードを追加する手順:
      1. 本 enum に値を追加
      2. ``frontend/src/constants/errorCodes.ts:ERROR_CODES`` に文字列を追加
      3. ``frontend/src/constants/errorMessages.ts:ERROR_CONFIG`` にメッセージと recovery を追加
    """

    # 認証
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    # GitHub
    GITHUB_RATE_LIMITED = "GITHUB_RATE_LIMITED"
    GITHUB_USER_NOT_FOUND = "GITHUB_USER_NOT_FOUND"
    # LLM
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    # バリデーション
    VALIDATION_ERROR = "VALIDATION_ERROR"
    # 外部 API
    QIITA_RATE_LIMITED = "QIITA_RATE_LIMITED"
    # アプリケーション全体
    RATE_LIMITED = "RATE_LIMITED"
    # サーバー
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppErrorResponse(BaseModel):
    code: ErrorCode
    message: str
    action: str | None = None
    retry_after: int | None = None
    error_id: str | None = None

    model_config = ConfigDict(use_enum_values=True)


def generate_error_id() -> str:
    """Cloud Logging と突合しやすい短いエラー ID を生成する。"""
    return uuid4().hex[:12]


def build_app_error_response(
    *,
    code: ErrorCode,
    message: str,
    action: str | None = None,
    retry_after: int | None = None,
    error_id: str | None = None,
) -> AppErrorResponse:
    return AppErrorResponse(
        code=code,
        message=message,
        action=action,
        retry_after=retry_after,
        error_id=error_id,
    )


def raise_app_error(
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    action: str | None = None,
    retry_after: int | None = None,
    headers: dict[str, str] | None = None,
) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail=build_app_error_response(
            code=code,
            message=message,
            action=action,
            retry_after=retry_after,
        ).model_dump(exclude_none=True),
        headers=headers,
    )


def infer_error_code(status_code: int, detail: Any = None) -> ErrorCode:
    """既存の文字列 detail からも可能な範囲でエラーコードを推定する。"""
    message = ""
    if isinstance(detail, dict):
        if isinstance(detail.get("code"), str):
            try:
                return ErrorCode(detail["code"])
            except ValueError:
                pass
        raw_message = detail.get("message")
        if isinstance(raw_message, str):
            message = raw_message
    elif isinstance(detail, str):
        message = detail

    if "GitHubユーザーが見つかりません" in message:
        return ErrorCode.GITHUB_USER_NOT_FOUND
    if "タイムアウト" in message:
        return ErrorCode.LLM_TIMEOUT
    if ("LLM" in message or "AI " in message or "AI分析" in message) and "利用できません" in message:
        return ErrorCode.LLM_UNAVAILABLE

    if status_code == 401:
        return ErrorCode.AUTH_REQUIRED
    if status_code == 429:
        return ErrorCode.RATE_LIMITED
    if status_code in (400, 404, 409, 422):
        return ErrorCode.VALIDATION_ERROR
    return ErrorCode.INTERNAL_ERROR


def normalize_http_exception_detail(
    *,
    status_code: int,
    detail: Any,
    error_id: str,
) -> AppErrorResponse:
    """FastAPI の既存 HTTPException を AppErrorResponse に正規化する。"""
    if isinstance(detail, dict) and isinstance(detail.get("code"), str) and isinstance(
        detail.get("message"), str
    ):
        payload = {**detail, "error_id": detail.get("error_id") or error_id}
        return AppErrorResponse.model_validate(payload)

    if isinstance(detail, str):
        message = detail
    elif detail is None:
        message = "予期しないエラーが発生しました。"
    else:
        message = str(detail)

    return build_app_error_response(
        code=infer_error_code(status_code, detail),
        message=message,
        error_id=error_id,
    )


def infer_async_error_code(error_message: str | None) -> ErrorCode | None:
    if not error_message:
        return None
    return infer_error_code(500, error_message)


def resolve_async_error_code(error_message: str | None) -> str | None:
    """非同期タスクのエラーメッセージからエラーコード文字列を解決する。

    ルーターで繰り返す `infer_async_error_code(msg).value if msg and ... else None`
    パターンを一か所に集約する。
    """
    if not error_message:
        return None
    code = infer_async_error_code(error_message)
    return code.value if code else None
