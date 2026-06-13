"""クレジット残高の検証・消費・付与のビジネスロジック（ADR-0012）。

HTTP 知識（ステータスコード・HTTPException）は持ち込まない。
router 側で ``InsufficientCreditsError`` → 402 ``INSUFFICIENT_CREDITS`` に変換する。
"""

import logging

from sqlalchemy.orm import Session

from ...repositories.billing import BillingRepository
from ..agent.chat_service import AgentUsage
from ..agent.model_catalog import calculate_credit_cost, get_model_spec

logger = logging.getLogger(__name__)

# 台帳の transaction_type（models/billing.py のコメントと同期）
TRANSACTION_TYPE_CONSUMPTION = "consumption"
TRANSACTION_TYPE_ADMIN_GRANT = "admin_grant"
TRANSACTION_TYPE_PURCHASE = "purchase"


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


def record_chat_usage(db: Session, user_id: str, usage: AgentUsage) -> int | None:
    """チャット 1 回分の使用量を記録し、有料モデルならクレジットを消費する。

    無料モデルは使用ログのみ記録して None を返す。有料モデルは残高減算・台帳追記・
    使用ログ記録を単一トランザクションで原子的に確定し、適用後残高を返す。記録の
    失敗（途中での例外）は全体を rollback して呼び出し元へ伝播させる
    （課金漏れ・課金とログの不整合を黙って通さない方針 / ADR-0012）。
    """
    cost = calculate_credit_cost(usage.model, usage.input_tokens, usage.output_tokens)
    balance_after = BillingRepository(db, user_id).record_chat_consumption(
        amount=-cost,
        transaction_type=TRANSACTION_TYPE_CONSUMPTION,
        description=f"Agent チャット（{usage.model}）",
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


def grant_credits(
    db: Session,
    user_id: str,
    amount: int,
    *,
    transaction_type: str,
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
