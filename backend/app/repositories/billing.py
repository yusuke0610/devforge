"""クレジット課金リポジトリ（ADR-0012）。

残高更新は ``UPDATE users SET credit_balance = credit_balance + :delta`` の
原子的 UPDATE で行い、同一トランザクション内で台帳（credit_transactions）へ
追記してから commit する。Cloud Run 単一インスタンス（ADR-0005）前提のため
分散ロックは持たない。
"""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models.billing import AgentUsageLog, CreditTransaction
from ..models.user import User


class BillingRepository:
    """クレジット残高・台帳・使用ログのデータアクセス層。"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get_balance(self) -> int:
        """現在のクレジット残高を返す。"""
        balance = self.db.scalar(
            select(User.credit_balance).where(User.id == self.user_id)
        )
        return balance or 0

    def apply_transaction(
        self,
        *,
        amount: int,
        transaction_type: str,
        description: str | None = None,
        stripe_session_id: str | None = None,
    ) -> int:
        """残高を原子的に増減し、台帳へ追記して適用後残高を返す。

        amount は符号付き（付与: 正 / 消費: 負）。残高更新と台帳追記を
        同一トランザクションで commit する（片方だけ反映される状態を作らない）。
        """
        self.db.execute(
            update(User)
            .where(User.id == self.user_id)
            .values(credit_balance=User.credit_balance + amount)
        )
        balance_after = self.db.scalar(
            select(User.credit_balance).where(User.id == self.user_id)
        )
        if balance_after is None:
            # CASCADE 削除等でユーザーが消えた直後の競合。残高不明のまま進めない
            self.db.rollback()
            raise RuntimeError(f"残高更新対象のユーザーが存在しません: {self.user_id}")
        self.db.add(
            CreditTransaction(
                user_id=self.user_id,
                amount=amount,
                balance_after=balance_after,
                transaction_type=transaction_type,
                description=description,
                stripe_session_id=stripe_session_id,
            )
        )
        self.db.commit()
        return balance_after

    def add_usage_log(
        self, *, model_alias: str, input_tokens: int, output_tokens: int, credit_cost: int
    ) -> None:
        """Agent チャット 1 回分の使用ログを記録する（無料モデルも記録する）。"""
        self.db.add(
            AgentUsageLog(
                user_id=self.user_id,
                model_alias=model_alias,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                credit_cost=credit_cost,
            )
        )
        self.db.commit()

    def list_transactions(self, limit: int = 50) -> list[CreditTransaction]:
        """台帳履歴を新しい順に返す。"""
        stmt = (
            select(CreditTransaction)
            .where(CreditTransaction.user_id == self.user_id)
            .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
