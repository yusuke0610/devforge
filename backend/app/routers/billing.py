"""クレジット課金エンドポイント（ADR-0012）。

Phase 1: 残高照会・台帳履歴・管理者付与のみ。
Phase 2 で Stripe Checkout（購入セッション作成・Webhook 入金）を追加する。
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.errors import ErrorCode, raise_app_error
from ..core.messages import get_error
from ..core.security.auth import get_current_user
from ..core.security.dependencies import verify_admin_token
from ..db import get_db
from ..models import User
from ..repositories import BillingRepository, UserRepository
from ..schemas.billing import (
    AdminCreditGrantRequest,
    AgentUsageSummaryEntry,
    CreditBalanceResponse,
    CreditTransactionResponse,
)
from ..services.billing import credit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/balance", response_model=CreditBalanceResponse)
def get_credit_balance(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CreditBalanceResponse:
    """ログインユーザーのクレジット残高を返す。"""
    return CreditBalanceResponse(balance=BillingRepository(db, user.id).get_balance())


@router.get("/transactions", response_model=list[CreditTransactionResponse])
def list_credit_transactions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CreditTransactionResponse]:
    """クレジット台帳履歴（付与・消費）を新しい順に返す。"""
    transactions = BillingRepository(db, user.id).list_transactions()
    return [CreditTransactionResponse.model_validate(t) for t in transactions]


@router.get("/usage-summary", response_model=list[AgentUsageSummaryEntry])
def get_usage_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AgentUsageSummaryEntry]:
    """モデル別の使用量サマリ（チャット回数・トークン・消費クレジット）を返す。

    モデル選択モーダルで「あなたの利用実績」を表示するために使う。残りチャット回数の
    目安は残高と組み合わせてフロントで算出する。
    """
    rows = BillingRepository(db, user.id).usage_summary()
    return [
        AgentUsageSummaryEntry(
            model=row.model_alias,
            chat_count=row.chat_count,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            credit_cost=row.credit_cost,
        )
        for row in rows
    ]


@router.post("/admin/grant", response_model=CreditBalanceResponse)
def admin_grant_credits(
    body: AdminCreditGrantRequest,
    _: None = Depends(verify_admin_token),
    db: Session = Depends(get_db),
) -> CreditBalanceResponse:
    """管理者がユーザーへクレジットを付与する（Phase 1 の残高調整・テスト用）。

    ADMIN_TOKEN（Bearer）認証。Stripe 導入後も返金・補填時の残高調整用に残す。
    """
    target = UserRepository(db).get_by_username(body.username)
    if target is None:
        raise_app_error(
            status_code=404,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("billing.grant_user_not_found"),
        )
    balance_after = credit_service.grant_credits(
        db,
        target.id,
        body.amount,
        transaction_type=credit_service.TRANSACTION_TYPE_ADMIN_GRANT,
        description=body.description,
    )
    logger.info(
        "管理者クレジット付与: username=%s amount=%d balance_after=%d",
        body.username,
        body.amount,
        balance_after,
    )
    return CreditBalanceResponse(balance=balance_after)
