"""PDF 職務経歴書インポートタスクのキャッシュレコード。"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


def _default_expires_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=1)


class ResumeImport(Base):
    """PDF インポートタスクのキャッシュレコード。

    run 完了または失敗後に pdf_blob は null クリアされる。
    resumes テーブルへの INSERT は行わず、フォームへの反映はフロントエンド側が担う。
    """

    __tablename__ = "resume_imports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    pdf_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_resume_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    judge_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_default_expires_at
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
