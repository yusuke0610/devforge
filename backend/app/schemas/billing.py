"""クレジット課金の Pydantic スキーマ（ADR-0012）。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreditBalanceResponse(BaseModel):
    """クレジット残高。"""

    balance: int


class CreditTransactionResponse(BaseModel):
    """クレジット台帳エントリ 1 件（履歴表示用）。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    # 符号付きの増減量（付与: 正 / 消費: 負）
    amount: int
    balance_after: int
    # consumption / admin_grant / purchase
    transaction_type: str
    description: str | None = None
    created_at: datetime


class AdminCreditGrantRequest(BaseModel):
    """管理者によるクレジット付与（Phase 1 の残高調整・テスト用）。"""

    username: str = Field(min_length=1, max_length=120)
    # 1 回の付与上限は 1,000 万クレジット（$1,000 相当）。誤入力の桁あふれを防ぐ
    amount: int = Field(gt=0, le=10_000_000)
    description: str | None = Field(default=None, max_length=200)
