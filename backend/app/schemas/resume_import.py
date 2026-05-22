"""職務経歴書 PDF インポートの API スキーマ。"""

from uuid import UUID

from pydantic import BaseModel

from .resume import ResumeBase


class ResumeImportStartResponse(BaseModel):
    """POST /api/resumes/import の 202 レスポンス。"""

    import_id: UUID


class ResumeImportStatusResponse(BaseModel):
    """GET /api/resumes/import/{id}/status のレスポンス。"""

    status: str
    error_message: str | None = None
    error_code: str | None = None
    judge_reason: str | None = None


class ResumeImportResultResponse(BaseModel):
    """GET /api/resumes/import/{id}/result のレスポンス。"""

    result: ResumeBase
    is_resume: bool
    judge_reason: str | None = None
