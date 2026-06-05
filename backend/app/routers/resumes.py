import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..core.messages import get_error, get_success
from ..core.security.auth import get_current_user
from ..db import get_db
from ..models import Resume, User
from ..repositories import ResumeRepository
from ..schemas import (
    ResumeCreate,
    ResumePreviewResponse,
    ResumeResponse,
    ResumeUpdate,
)
from ..services.markdown.generators.resume_generator import (
    build_resume_markdown,
)
from ..services.pdf.generators.resume_generator import (
    build_resume_pdf,
    build_resume_preview,
)
from .download_utils import stream_markdown, stream_pdf

router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def _resume_to_payload(resume: Resume) -> dict:
    """Resume ORM から PDF/Markdown 生成用 payload を組み立てる。"""
    return {
        "full_name": resume.full_name,
        "career_summary": resume.career_summary,
        "self_pr": resume.self_pr,
        "experiences": resume.experiences,
        "qualifications": resume.qualifications,
    }


def _get_resume_or_404(repository: ResumeRepository, resume_id: uuid.UUID) -> Resume:
    """指定 ID の Resume を取得し、未存在なら 404 を上げる。

    `get_by_id → if not resume: raise HTTPException(404, ...)` の同一パターンを集約。
    """
    resume = repository.get_by_id(str(resume_id))
    if not resume:
        raise HTTPException(
            status_code=404,
            detail=get_error("document.not_found", document="職務経歴書"),
        )
    return resume


@router.post("", response_model=ResumeResponse, status_code=201)
def create_resume(
    payload: ResumeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeResponse:
    repository = ResumeRepository(db, current_user.id)
    try:
        return repository.create(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=get_error(str(exc), document="職務経歴書"),
        ) from exc


@router.post("/preview", response_model=ResumePreviewResponse)
def preview_resume(
    payload: ResumeCreate,
    current_user: User = Depends(get_current_user),
) -> ResumePreviewResponse:
    """保存せずに、職務経歴書を PDF と同じレイアウトに整形した HTML と画面用 CSS を返す。

    左右 diff プレビュー（左=保存済み / 右=編集中）の描画に使う。HTML 内の各値ノードには
    form パス（``data-fp``）が付与され、FE が変更箇所のハイライト・スクロール先特定に使う。
    DB は更新しない。WeasyPrint を通さず HTML 文字列生成のみのため軽量。
    """
    html, css = build_resume_preview(payload.model_dump())
    return ResumePreviewResponse(html=html, css=css)


@router.get("/latest", response_model=ResumeResponse)
def get_latest_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeResponse:
    repository = ResumeRepository(db, current_user.id)
    resume = repository.get_latest()
    if not resume:
        raise HTTPException(
            status_code=404,
            detail=get_error("document.not_found", document="職務経歴書"),
        )
    return resume


@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeResponse:
    repository = ResumeRepository(db, current_user.id)
    return _get_resume_or_404(repository, resume_id)


@router.put("/{resume_id}", response_model=ResumeResponse)
def update_resume(
    resume_id: uuid.UUID,
    payload: ResumeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResumeResponse:
    repository = ResumeRepository(db, current_user.id)
    resume = _get_resume_or_404(repository, resume_id)
    return repository.update(resume, payload.model_dump())


@router.delete("")
def delete_resume(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    repository = ResumeRepository(db, current_user.id)
    if not repository.delete():
        raise HTTPException(
            status_code=404,
            detail=get_error("document.not_found", document="職務経歴書"),
        )
    return {"message": get_success("document.deleted", document="職務経歴書")}


@router.get("/{resume_id}/pdf")
def download_resume_pdf(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    repository = ResumeRepository(db, current_user.id)
    resume = _get_resume_or_404(repository, resume_id)
    pdf_bytes = build_resume_pdf(_resume_to_payload(resume))
    return stream_pdf(pdf_bytes, f"career-resume-{resume.id}.pdf")


@router.get("/{resume_id}/markdown")
def download_resume_markdown(
    resume_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    repository = ResumeRepository(db, current_user.id)
    resume = _get_resume_or_404(repository, resume_id)
    md_text = build_resume_markdown(_resume_to_payload(resume))
    return stream_markdown(md_text, f"career-resume-{resume.id}.md")
