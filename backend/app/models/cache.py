import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class GitHubLinkCache(Base):
    """GitHub 連携結果のキャッシュ。ユーザーごとに最新の連携結果を1件保持する。"""

    __tablename__ = "github_link_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False
    )
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed", server_default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    # 「連携自体は完了したが部分的に欠落した」非致命的状況を残す。
    # error_message は真の失敗のみに使う。
    warning_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
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


class ResumeDraftCache(Base):
    """経歴書ドラフト生成タスクの状態と生成結果のキャッシュ（ADR-0018 / 非同期化）。

    ユーザーごとに最新のドラフト生成 1 件を保持する（``resumes`` テーブルとは無関係。
    確定した職務経歴書は ``Resume`` が正本で、本テーブルは連携ドメイン側の生成キャッシュ）。
    ``result`` には LLM が生成したドラフト payload（``build_resume_pdf`` の入力 dict）を保存し、
    ダウンロード時に PDF を再レンダリングする（DB にバイナリを持たない）。

    ``status`` / ``error_message`` / ``retry_count`` / ``started_at`` / ``completed_at`` を持ち、
    非同期タスク基盤（``AsyncTaskCacheService`` の ``_AsyncTaskRecord`` Protocol）に適合する。
    """

    __tablename__ = "resume_draft_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), unique=True, nullable=False
    )
    # LLM 生成のドラフト payload（build_resume_pdf の入力 dict）。完了時のみ非 NULL。
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="completed", server_default="completed"
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
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
