"""Stripe Checkout 連携（ADR-0012 Phase 2）。

カード情報は Stripe ホストの決済ページで入力され、自サーバーは一切扱わない
（PCI DSS 非対象）。入金確定は Webhook（``checkout.session.completed``）が正で、
署名検証を必須とする。リダイレクト戻り（success_url）は付与に使わない。

HTTP 知識（HTTPException・ステータスコード）は持ち込まない。router 側で本モジュールの
ドメイン例外を ``raise_app_error`` へ変換する。
"""

import logging
from dataclasses import dataclass

import stripe

from ...core import settings

logger = logging.getLogger(__name__)

# Checkout の通貨。日本円は Stripe のゼロ十進通貨のため unit_amount = 円額そのもの
_CURRENCY = "jpy"
_PRODUCT_NAME = "DevForge クレジット"
# 入金確定イベント。これ以外は付与対象外として無視する
CHECKOUT_COMPLETED_EVENT = "checkout.session.completed"


class StripeNotConfiguredError(Exception):
    """STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET が未設定（決済機能が無効）。"""


class StripeCheckoutError(Exception):
    """Stripe API 呼び出しに失敗した（Checkout セッションを作成できない）。"""


class WebhookVerificationError(Exception):
    """Webhook の署名検証に失敗した（不正なペイロード / 署名）。"""


@dataclass(frozen=True)
class CompletedPurchase:
    """入金確定済みの購入情報（Webhook から付与に使う）。"""

    user_id: str
    credits: int
    stripe_session_id: str


def create_checkout_session(
    *, user_id: str, credits: int, success_url: str, cancel_url: str
) -> str:
    """クレジット購入の Checkout Session を作成し、決済ページ URL を返す。

    1 クレジット = ¥1（ADR-0012）。``price_data`` で動的に価格を渡し、Stripe ダッシュボードの
    Price オブジェクトに依存しない。``metadata`` に user_id / credits を載せ、Webhook 側で
    付与に使う。

    Raises:
        StripeNotConfiguredError: STRIPE_SECRET_KEY が未設定。
        StripeCheckoutError: Stripe API 呼び出しに失敗、または URL が得られなかった。
    """
    secret_key = settings.get_stripe_secret_key()
    if not secret_key:
        raise StripeNotConfiguredError("STRIPE_SECRET_KEY が設定されていません")
    try:
        session = stripe.checkout.Session.create(
            api_key=secret_key,
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": _CURRENCY,
                        "product_data": {"name": _PRODUCT_NAME},
                        "unit_amount": credits,  # 1cr=¥1 / JPY はゼロ十進
                    },
                    "quantity": 1,
                }
            ],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=user_id,
            metadata={"user_id": user_id, "credits": str(credits)},
        )
    except stripe.StripeError as exc:
        # API キー等の秘密情報を含めないため例外型のみログに残す
        logger.warning("Stripe Checkout セッション作成に失敗: %s", type(exc).__name__)
        raise StripeCheckoutError(f"Stripe error: {type(exc).__name__}") from exc

    if not session.url:
        raise StripeCheckoutError("Stripe が Checkout URL を返しませんでした")
    return session.url


def parse_webhook_event(payload: bytes, signature: str | None) -> stripe.Event:
    """Webhook ペイロードの署名を検証し、イベントを返す（fail-closed）。

    署名検証は STRIPE_WEBHOOK_SECRET 必須。秘密未設定・署名欠落・検証失敗・不正ペイロードは
    例外を送出し、付与処理に進ませない。

    Raises:
        StripeNotConfiguredError: STRIPE_WEBHOOK_SECRET が未設定。
        WebhookVerificationError: 署名欠落・検証失敗・不正ペイロード。
    """
    webhook_secret = settings.get_stripe_webhook_secret()
    if not webhook_secret:
        raise StripeNotConfiguredError("STRIPE_WEBHOOK_SECRET が設定されていません")
    if not signature:
        raise WebhookVerificationError("Stripe-Signature ヘッダーがありません")
    try:
        return stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        logger.warning("Stripe Webhook 署名検証に失敗: %s", type(exc).__name__)
        raise WebhookVerificationError(
            f"Webhook verification failed: {type(exc).__name__}"
        ) from exc


def extract_completed_purchase(event: stripe.Event) -> CompletedPurchase | None:
    """入金確定イベントから付与情報を取り出す。付与対象でなければ ``None``。

    対象外イベント・未払い（``payment_status != "paid"``）・metadata 欠落/不正は ``None`` を返す
    （Webhook は 200 で受領しつつ付与をスキップする / 課金漏れより安全側）。
    """
    if event["type"] != CHECKOUT_COMPLETED_EVENT:
        return None
    session = event["data"]["object"]
    if session.get("payment_status") != "paid":
        logger.info(
            "Checkout 未払いのため付与をスキップ: status=%s", session.get("payment_status")
        )
        return None
    session_id = session.get("id")
    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id")
    raw_credits = metadata.get("credits")
    if not session_id or not user_id or raw_credits is None:
        logger.warning("Checkout イベントの metadata が不足: session_id=%s", session_id)
        return None
    try:
        credits = int(raw_credits)
    except (TypeError, ValueError):
        logger.warning("Checkout metadata の credits が不正: %r", raw_credits)
        return None
    if credits <= 0:
        logger.warning("Checkout metadata の credits が非正: %d", credits)
        return None
    return CompletedPurchase(
        user_id=user_id, credits=credits, stripe_session_id=session_id
    )
