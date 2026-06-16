"""クレジット課金の Pydantic スキーマ（ADR-0012）。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# 任意クレジット購入の入力範囲（誤入力の桁あふれ・極小購入を防ぐ）。
# frontend/src/utils/creditEstimate.ts の MIN/MAX_PURCHASE_CREDITS と一致させる
MIN_PURCHASE_CREDITS = 100
MAX_PURCHASE_CREDITS = 1_000_000


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


class CreditPackResponse(BaseModel):
    """購入可能なクレジットパック 1 種（トークン購入画面用 / ADR-0012）。"""

    id: str
    name: str
    price_jpy: int
    credits: int


class ModelRateEntry(BaseModel):
    """モデル別の標準消費レート（回数目安の算出用 / ADR-0012）。

    1 クレジット = ¥1。``baseline_credits_per_chat`` は標準的な 1 回の消費の概算で、
    フロントが残高・パックを「Sonnet 約N回」に換算するのに使う（無料モデルは 0）。
    """

    model: str
    is_free: bool
    baseline_credits_per_chat: int


class AgentUsageSummaryEntry(BaseModel):
    """モデル別の使用量サマリ 1 件（モデル選択モーダルの利用実績表示用 / ADR-0012）。"""

    # model_catalog.py のエイリアス（haiku / sonnet）
    model: str
    chat_count: int
    input_tokens: int
    output_tokens: int
    # 消費クレジット合計（無料モデルは 0）
    credit_cost: int


class CheckoutSessionRequest(BaseModel):
    """クレジット購入の Stripe Checkout セッション作成リクエスト（ADR-0012 Phase 2）。"""

    # 1 クレジット = ¥1。入力範囲は誤入力の桁あふれ・極小購入を防ぐ
    credits: int = Field(ge=MIN_PURCHASE_CREDITS, le=MAX_PURCHASE_CREDITS)


class CheckoutSessionResponse(BaseModel):
    """Stripe Checkout 決済ページの URL。フロントはこの URL へリダイレクトする。"""

    checkout_url: str


class AdminCreditGrantRequest(BaseModel):
    """管理者によるクレジット付与（Phase 1 の残高調整・テスト用）。"""

    username: str = Field(min_length=1, max_length=120)
    # 1 回の付与上限は 1,000 万クレジット（$1,000 相当）。誤入力の桁あふれを防ぐ
    amount: int = Field(gt=0, le=10_000_000)
    description: str | None = Field(default=None, max_length=200)
