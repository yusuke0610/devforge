"""
職務経歴書 PDF インポート API エンドポイント。

POST   /api/resumes/import          — PDF アップロード、インポート開始（202 非同期）
GET    /api/resumes/import/{id}/status  — ポーリング用ステータス確認
GET    /api/resumes/import/{id}/result  — 抽出結果取得（completed のみ 200）
"""

import io
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from ..core.errors import ErrorCode, raise_app_error, resolve_async_error_code
from ..core.security.auth import get_current_user
from ..core.security.dependencies import limiter
from ..db import get_db
from ..models import User
from ..models.resume_import import ResumeImport
from ..schemas.resume import ResumeBase
from ..schemas.resume_import import (
    ResumeImportResultResponse,
    ResumeImportStartResponse,
    ResumeImportStatusResponse,
)
from ..schemas.shared import ProgressResponse
from ..services.tasks import AsyncTaskCacheService, TaskType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumes/import", tags=["resume-imports"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_MAX_PAGES = 20
_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB ずつ読み込み、サイズ超過を早期検知する


@router.post("", response_model=ResumeImportStartResponse, status_code=202)
@limiter.limit("10/minute")
async def start_import(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """PDF をアップロードしてインポートタスクを開始する。"""
    if file.content_type != "application/pdf":
        raise_app_error(
            status_code=422,
            code=ErrorCode.RESUME_IMPORT_INVALID,
            message="PDF をアップロードしてください。",
            action="ファイル種別を確認して再試行してください",
        )

    buffer = bytearray()
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > _MAX_FILE_SIZE:
            await file.close()
            raise_app_error(
                status_code=422,
                code=ErrorCode.RESUME_IMPORT_INVALID,
                message="ファイルサイズは 10 MB 以下にしてください。",
                action="ファイルを圧縮するか別の PDF をお試しください",
            )
    pdf_bytes = bytes(buffer)

    # ページ数チェック（pdfplumber は純粋 Python のため router 内で使用可能）
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if len(pdf.pages) > _MAX_PAGES:
                raise_app_error(
                    status_code=422,
                    code=ErrorCode.RESUME_IMPORT_INVALID,
                    message=f"PDF は {_MAX_PAGES} ページ以下にしてください。",
                    action="ページ数を確認して再試行してください",
                )
    except Exception as exc:
        # raise_app_error は HTTPException を継承しているので再 raise
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise
        logger.warning("PDF ページ数チェックに失敗しました", exc_info=True)
        raise_app_error(
            status_code=422,
            code=ErrorCode.RESUME_IMPORT_INVALID,
            message="PDF の読み込みに失敗しました。別のファイルをお試しください。",
            action="PDF ファイルが破損していないか確認してください",
        )

    record = ResumeImport(user_id=current_user.id, pdf_blob=pdf_bytes)
    db.add(record)
    db.commit()
    db.refresh(record)

    service = AsyncTaskCacheService(db, record)
    try:
        await service.dispatch(
            background_tasks,
            TaskType.RESUME_IMPORT,
            {"user_id": current_user.id, "import_id": record.id},
            failure_message="インポートタスクの開始に失敗しました",
            logger=logger,
        )
    except Exception:
        # dispatch 失敗時、service 側で status=dead_letter / error_message は設定済み。
        # ここでは加えて pdf_blob をクリアし、機微データを残さない。
        try:
            record.pdf_blob = None
            db.commit()
            logger.info(
                "ResumeImport の pdf_blob をクリアしました (dispatch 失敗)",
                extra={"import_id": record.id},
            )
        except Exception:
            logger.warning(
                "pdf_blob のクリアに失敗しました (無視)",
                exc_info=True,
                extra={"import_id": record.id},
            )
        raise_app_error(
            status_code=500,
            code=ErrorCode.INTERNAL_ERROR,
            message="インポートタスクの開始に失敗しました。しばらく待ってから再試行してください。",
            action="しばらく待ってから再試行してください",
        )

    return ResumeImportStartResponse(import_id=record.id)


@router.get("/{import_id}/status", response_model=ResumeImportStatusResponse)
def get_import_status(
    import_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """インポートタスクのステータスを返す（軽量ポーリング用）。"""
    record = db.query(ResumeImport).filter_by(id=import_id, user_id=current_user.id).first()
    if not record:
        raise_app_error(
            status_code=404,
            code=ErrorCode.VALIDATION_ERROR,
            message="インポートレコードが見つかりません。",
            action="インポートをやり直してください",
        )

    return ResumeImportStatusResponse(
        status=record.status,
        error_message=record.error_message,
        error_code=resolve_async_error_code(record.error_message),
        judge_reason=record.judge_reason,
    )


@router.get("/{import_id}/progress", response_model=ProgressResponse)
async def get_import_progress(
    import_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """インポートタスクの進捗（ステップ）情報を返す。Redis にデータが無い場合は step_index=0 のデフォルト。"""
    from ..services.progress_service import get_progress

    record = db.query(ResumeImport).filter_by(id=import_id, user_id=current_user.id).first()
    if not record:
        raise_app_error(
            status_code=404,
            code=ErrorCode.VALIDATION_ERROR,
            message="インポートレコードが見つかりません。",
            action="インポートをやり直してください",
        )

    data = await get_progress(record.id, default_total_steps=3)
    return ProgressResponse(**data)


@router.get("/{import_id}/result", response_model=ResumeImportResultResponse)
def get_import_result(
    import_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """抽出結果を返す。completed 以外のステータスでは 409 を返す。"""
    record = db.query(ResumeImport).filter_by(id=import_id, user_id=current_user.id).first()
    if not record:
        raise_app_error(
            status_code=404,
            code=ErrorCode.VALIDATION_ERROR,
            message="インポートレコードが見つかりません。",
            action="インポートをやり直してください",
        )

    if record.status != "completed":
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=f"インポートはまだ完了していません（現在: {record.status}）。",
            action="しばらく待ってから再試行してください",
        )

    parsed = json.loads(record.result_json)
    return ResumeImportResultResponse(
        result=ResumeBase(**parsed),
        is_resume=bool(record.is_resume_flag),
        judge_reason=record.judge_reason,
    )
