"""クレジット課金エンドポイント（ADR-0012）。

Phase 1: 残高照会・台帳履歴・管理者付与。
Phase 2: Stripe Checkout（購入セッション作成・Webhook 入金）。
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..core.errors import ErrorCode, raise_app_error
from ..core.messages import get_error
from ..core.security.auth import get_current_user
from ..core.security.dependencies import limiter, verify_admin_token
from ..core.settings import get_billing_return_base_url
from ..db import get_db
from ..models import User
from ..repositories import BillingRepository, UserRepository
from ..schemas.billing import (
    AdminCreditGrantRequest,
    AgentUsageSummaryEntry,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CreditBalanceResponse,
    CreditPackResponse,
    CreditTransactionResponse,
    ModelRateEntry,
)
from ..services.agent.model_catalog import MODEL_CATALOG, baseline_credits_per_chat
from ..services.billing import credit_service, stripe_service
from ..services.billing.pricing import CREDIT_PACKS

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


@router.get("/packs", response_model=list[CreditPackResponse])
def list_credit_packs(
    _: User = Depends(get_current_user),
) -> list[CreditPackResponse]:
    """購入可能なクレジットパック一覧を返す（トークン購入画面用 / ADR-0012）。

    価格・付与クレジットの正本は services/billing/pricing.py。
    """
    return [
        CreditPackResponse(
            id=pack.id, name=pack.name, price_jpy=pack.price_jpy, credits=pack.credits
        )
        for pack in CREDIT_PACKS
    ]


@router.get("/model-rates", response_model=list[ModelRateEntry])
def list_model_rates(
    _: User = Depends(get_current_user),
) -> list[ModelRateEntry]:
    """モデル別の標準消費レート（回数目安の算出用 / ADR-0012）を返す。

    フロントは残高・パック・モデルカードを「Sonnet 約N回」に換算するのに使う。
    利用実績のあるユーザーは usage-summary の実測平均を優先し、本値は新規ユーザーの
    フォールバックとして使う。
    """
    return [
        ModelRateEntry(
            model=alias,
            is_free=spec.is_free,
            baseline_credits_per_chat=baseline_credits_per_chat(alias),
        )
        for alias, spec in MODEL_CATALOG.items()
    ]


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


@router.post("/checkout", response_model=CheckoutSessionResponse)
@limiter.limit("20/minute")
def create_checkout(
    request: Request,
    body: CheckoutSessionRequest,
    user: User = Depends(get_current_user),
) -> CheckoutSessionResponse:
    """クレジット購入の Stripe Checkout セッションを作成し、決済ページ URL を返す（ADR-0012）。

    外部 API（Stripe）を呼ぶ高コスト endpoint のため rate limit を付与する。
    入金確定は Webhook（checkout.session.completed）が正であり、本エンドポイントは
    決済ページへ誘導する URL を返すだけで残高は更新しない。
    """
    base_url = get_billing_return_base_url()
    success_url = f"{base_url}/billing?checkout=success"
    cancel_url = f"{base_url}/billing?checkout=cancel"
    try:
        checkout_url = stripe_service.create_checkout_session(
            user_id=user.id,
            credits=body.credits,
            success_url=success_url,
            cancel_url=cancel_url,
        )
    except stripe_service.StripeNotConfiguredError:
        raise_app_error(
            status_code=503,
            code=ErrorCode.PAYMENT_ERROR,
            message=get_error("billing.checkout_unavailable"),
        )
    except stripe_service.StripeCheckoutError:
        raise_app_error(
            status_code=502,
            code=ErrorCode.PAYMENT_ERROR,
            message=get_error("billing.checkout_failed"),
        )
    return CheckoutSessionResponse(checkout_url=checkout_url)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    """Stripe Webhook（checkout.session.completed）でクレジットを付与する（ADR-0012）。

    署名検証必須。入金確定はこのエンドポイントが正で、付与の冪等性は
    credit_transactions.stripe_session_id の UNIQUE 制約で担保する。呼び出し元は Stripe の
    ため get_current_user は付けない（認証 Cookie は届かない）。Cloudflare を経由せず
    Cloud Run へ直接届くため InternalSecretMiddleware の対象外にしてある（main.py 参照）。
    """
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    try:
        event = stripe_service.parse_webhook_event(payload, signature)
    except stripe_service.StripeNotConfiguredError:
        raise_app_error(
            status_code=503,
            code=ErrorCode.PAYMENT_ERROR,
            message=get_error("billing.webhook_unavailable"),
        )
    except stripe_service.WebhookVerificationError:
        raise_app_error(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("billing.webhook_invalid"),
        )

    purchase = stripe_service.extract_completed_purchase(event)
    if purchase is not None:
        target = UserRepository(db).get_by_id(purchase.user_id)
        if target is None:
            # 付与対象が存在しない（退会等）。再送しても解決しないため 200 で受領する
            logger.warning(
                "Webhook 付与対象ユーザーが存在しません: user_id=%s", purchase.user_id
            )
        else:
            credit_service.record_stripe_purchase(
                db,
                purchase.user_id,
                purchase.credits,
                stripe_session_id=purchase.stripe_session_id,
            )
    return {"received": True}


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
