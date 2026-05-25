"""
職務経歴書 PDF インポート API エンドポイント。

POST /api/resumes/import/extract — PDF を割り当て候補ブロックに分解して返す
（同期・LLM 不使用・永続化なし）。フロントの取り込み補助 UI がこのブロックを
並べ、ユーザーがクリックで各フィールドへ流し込む。
"""

import logging

from fastapi import APIRouter, Depends, File, Request, UploadFile

from ..core.errors import ErrorCode, raise_app_error
from ..core.security.auth import get_current_user
from ..core.security.dependencies import limiter
from ..models import User
from ..schemas.resume_import import ResumeImportBlock, ResumeImportBlocksResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumes/import", tags=["resume-imports"])

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_MAX_PAGES = 20
_UPLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MB ずつ読み込み、サイズ超過を早期検知する


@router.post("/extract", response_model=ResumeImportBlocksResponse)
@limiter.limit("20/minute")
async def extract_blocks_for_assist(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """PDF を割り当て候補ブロックに分解して返す（同期・LLM 不使用・永続化なし）。

    pdfplumber でテキスト（行）と表（セル）を構造的に切り出すだけで、意味づけ
    （どの項目か）は行わない。フロントの取り込み補助 UI がこのブロックを並べ、
    ユーザーがクリックで各フィールドへ流し込む。PII を保存しないため DB には残さない。
    """
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

    from ..services.resume_import import pdf_extractor

    try:
        extracted = pdf_extractor.extract_blocks(pdf_bytes, max_pages=_MAX_PAGES)
    except Exception as exc:
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise
        logger.warning("PDF ブロック抽出に失敗しました", exc_info=True)
        raise_app_error(
            status_code=422,
            code=ErrorCode.RESUME_IMPORT_INVALID,
            message="PDF の読み込みに失敗しました。別のファイルをお試しください。",
            action="PDF ファイルが破損していないか確認してください",
        )

    if extracted.page_count > _MAX_PAGES:
        raise_app_error(
            status_code=422,
            code=ErrorCode.RESUME_IMPORT_INVALID,
            message=f"PDF は {_MAX_PAGES} ページ以下にしてください。",
            action="ページ数を確認して再試行してください",
        )

    if not extracted.has_text_layer:
        raise_app_error(
            status_code=422,
            code=ErrorCode.RESUME_IMPORT_INVALID,
            message="テキストを抽出できませんでした（スキャン PDF の可能性があります）。",
            action="文字を選択できる（テキスト付き）PDF をお試しください",
        )

    blocks = [
        ResumeImportBlock(id=index, kind=block.kind, text=block.text)
        for index, block in enumerate(extracted.blocks)
    ]
    return ResumeImportBlocksResponse(blocks=blocks)
