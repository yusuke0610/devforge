"""クレジット残高の検証・消費・付与のビジネスロジック（ADR-0012）。

HTTP 知識（ステータスコード・HTTPException）は持ち込まない。
router 側で ``InsufficientCreditsError`` → 402 ``INSUFFICIENT_CREDITS`` に変換する。
"""

import logging
from typing import Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...repositories.billing import BillingRepository
from ..agent.chat_service import AgentUsage
from ..agent.model_catalog import calculate_credit_cost, get_model_spec

logger = logging.getLogger(__name__)

# 台帳の transaction_type の閉じた集合（models/billing.py の transaction_type と同期）。
# 自由文字列を許すとタイポで台帳が汚れ、種別フィルタ/集計が壊れるため Literal で縛る
TransactionType = Literal["consumption", "admin_grant", "purchase"]
TRANSACTION_TYPE_CONSUMPTION: TransactionType = "consumption"
TRANSACTION_TYPE_ADMIN_GRANT: TransactionType = "admin_grant"
TRANSACTION_TYPE_PURCHASE: TransactionType = "purchase"


class InsufficientCreditsError(Exception):
    """有料モデルの利用に必要なクレジット残高が不足している。"""


def ensure_can_use_model(db: Session, user_id: str, model_alias: str) -> None:
    """有料モデル利用前の残高チェック。無料モデルは常に通す。

    残高 > 0 を要求する。実コストは LLM 応答後にしか確定しないため、
    チェック通過後の消費で残高が負になることは許容する（有界損失 / ADR-0012）。

    Raises:
        InsufficientCreditsError: 有料モデルで残高が 0 以下。
    """
    if get_model_spec(model_alias).is_free:
        return
    balance = BillingRepository(db, user_id).get_balance()
    if balance <= 0:
        raise InsufficientCreditsError(
            f"クレジット残高が不足しています: balance={balance}"
        )


def record_chat_usage(
    db: Session, user_id: str, usage: AgentUsage, *, description: str | None = None
) -> int | None:
    """LLM 利用 1 回分の使用量を記録し、有料モデルならクレジットを消費する。

    無料モデルは使用ログのみ記録して None を返す。有料モデルは残高減算・台帳追記・
    使用ログ記録を単一トランザクションで原子的に確定し、適用後残高を返す。記録の
    失敗（途中での例外）は全体を rollback して呼び出し元へ伝播させる
    （課金漏れ・課金とログの不整合を黙って通さない方針 / ADR-0012）。

    description は台帳の用途表示。省略時は既定のチャット文言（経歴書ドラフト生成
    など別用途の呼び出し元が上書きする / ADR-0018）。
    """
    cost = calculate_credit_cost(usage.model, usage.input_tokens, usage.output_tokens)
    balance_after = BillingRepository(db, user_id).record_chat_consumption(
        amount=-cost,
        transaction_type=TRANSACTION_TYPE_CONSUMPTION,
        description=description or f"Agent チャット（{usage.model}）",
        model_alias=usage.model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        credit_cost=cost,
    )
    if cost > 0:
        logger.info(
            "クレジット消費: model=%s in=%d out=%d cost=%d balance_after=%s",
            usage.model,
            usage.input_tokens,
            usage.output_tokens,
            cost,
            balance_after,
        )
    return balance_after


def record_usage_after_llm(
    db: Session, user_id: str, usage: AgentUsage, *, description: str | None = None
) -> None:
    """LLM 応答後のクレジット消費・使用ログ記録を、ストリームを開き直してから行う。

    LLM 呼び出しの await 中にリクエストの DB セッションがアイドルになり、libSQL
    （Hrana over HTTP）のストリームが idle timeout で失効する。失効したまま commit
    すると ``STREAM_EXPIRED`` で 400 → 500 になり課金記録も落ちるため、``db.close()`` で
    失効ストリームを解放してから記録する（次の SELECT/commit が新規コネクション＝新規
    Hrana ストリームを取得して正常に確定できる）。LLM を await する各 router 共通の後処理。
    """
    db.close()
    record_chat_usage(db, user_id, usage, description=description)


def grant_credits(
    db: Session,
    user_id: str,
    amount: int,
    *,
    transaction_type: TransactionType,
    description: str | None = None,
    stripe_session_id: str | None = None,
) -> int:
    """クレジットを付与し、適用後残高を返す。

    Phase 1 は管理者付与（admin_grant）のみ。Phase 2 で Stripe 購入（purchase）からも
    呼ばれる（stripe_session_id の UNIQUE 制約で二重付与を防ぐ / ADR-0012）。
    """
    if amount <= 0:
        # スキーマ検証をすり抜けた負値付与（実質消費）を防ぐ最終ガード
        raise ValueError(f"付与額は正の値であること: amount={amount}")
    return BillingRepository(db, user_id).apply_transaction(
        amount=amount,
        transaction_type=transaction_type,
        description=description,
        stripe_session_id=stripe_session_id,
    )


def record_stripe_purchase(
    db: Session,
    user_id: str,
    credits: int,
    *,
    stripe_session_id: str,
) -> int | None:
    """Stripe Checkout の入金確定でクレジットを付与する（Webhook から呼ぶ / ADR-0012）。

    付与の冪等性は ``credit_transactions.stripe_session_id`` の UNIQUE 制約で担保する。
    既に同一セッションで付与済みなら付与せず ``None`` を返す（Webhook 再送に対する冪等性）。
    付与した場合は適用後残高を返す。
    """
    repo = BillingRepository(db, user_id)
    if repo.find_by_stripe_session_id(stripe_session_id) is not None:
        logger.info("Stripe 購入は処理済みのため付与をスキップ: session_id=%s", stripe_session_id)
        return None
    try:
        balance_after = grant_credits(
            db,
            user_id,
            credits,
            transaction_type=TRANSACTION_TYPE_PURCHASE,
            description=f"クレジット購入（{credits:,} クレジット）",
            stripe_session_id=stripe_session_id,
        )
    except IntegrityError:
        # 事前チェックと INSERT の間に同一イベントが先に commit した競合。二重付与を防ぐ。
        # apply_transaction が既に rollback 済みのため、ここでは付与スキップとして扱う
        logger.info("Stripe 購入の競合を検出し付与をスキップ: session_id=%s", stripe_session_id)
        return None
    logger.info(
        "Stripe 購入を付与: user_id=%s credits=%d balance_after=%d session_id=%s",
        user_id,
        credits,
        balance_after,
        stripe_session_id,
    )
    return balance_after
