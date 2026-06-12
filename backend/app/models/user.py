import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, default=None)
    github_id: Mapped[int | None] = mapped_column(nullable=True, unique=True, default=None)
    github_token: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    refresh_jti: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    # プリペイドクレジット残高のキャッシュ（正本は credit_transactions 台帳 / ADR-0012）。
    # 事前チェック通過後の事後減算により一時的に負になりうる（有界損失を許容）
    credit_balance: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
