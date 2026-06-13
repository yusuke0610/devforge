"""クレジットパック（購入単位）の定義（ADR-0012）。

価格・付与クレジットの正本。トークン購入画面のパック一覧と、Phase 2 の
Stripe Checkout（`price_data` 動的生成）の双方がここを参照する。
為替変動は本ファイルの値の調整で吸収する（自動連動はしない）。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CreditPack:
    """購入クレジットパック 1 種。"""

    # Checkout の metadata で受け渡す安定 ID（変更しない）
    id: str
    name: str
    # 販売価格（日本円・税込想定）
    price_jpy: int
    # 付与クレジット（ボーナス込み）
    credits: int


# 目安: Sonnet 1 回 ≒ 270 クレジット。スタンダード以上はボーナス分を上乗せ
CREDIT_PACKS: list[CreditPack] = [
    CreditPack(id="starter", name="スターター", price_jpy=500, credits=30_000),
    CreditPack(id="standard", name="スタンダード", price_jpy=1_000, credits=65_000),
    CreditPack(id="pro", name="プロ", price_jpy=3_000, credits=210_000),
]

_PACKS_BY_ID = {pack.id: pack for pack in CREDIT_PACKS}


def get_pack(pack_id: str) -> CreditPack | None:
    """ID からパックを引く（未知の ID は None）。Phase 2 の Checkout 作成で使う。"""
    return _PACKS_BY_ID.get(pack_id)
