"""クレジット課金リポジトリ（ADR-0012）。

残高更新は ``UPDATE users SET credit_balance = credit_balance + :delta`` の
原子的 UPDATE で行い、同一トランザクション内で台帳（credit_transactions）へ
追記してから commit する。Cloud Run 単一インスタンス（ADR-0005）前提のため
分散ロックは持たない。
"""

from sqlalchemy import func, select, update
from sqlalchemy.engine import Row
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

    def _stage_balance_change(
        self,
        *,
        amount: int,
        transaction_type: str,
        description: str | None = None,
        stripe_session_id: str | None = None,
    ) -> int:
        """残高を原子的に増減し台帳へ追記する（commit はしない）。適用後残高を返す。

        commit は呼び出し側の責務。単独付与（``apply_transaction``）と、消費＋使用ログを
        1 トランザクションにまとめる用途（``record_chat_consumption``）の両方から使う。
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
            # CASCADE 削除等でユーザーが消えた直後の競合。残高不明のまま進めない。
            # rollback はトランザクション境界を持つ呼び出し側（commit する側）に委ねる
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
        return balance_after

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
        try:
            balance_after = self._stage_balance_change(
                amount=amount,
                transaction_type=transaction_type,
                description=description,
                stripe_session_id=stripe_session_id,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return balance_after

    def record_chat_consumption(
        self,
        *,
        amount: int,
        transaction_type: str,
        description: str,
        model_alias: str,
        input_tokens: int,
        output_tokens: int,
        credit_cost: int,
    ) -> int | None:
        """Agent チャット 1 回分の「クレジット消費 + 使用ログ」を単一トランザクションで確定する。

        amount は符号付き消費額（消費: 負 / 無料モデル: 0）。0 のときは残高更新・台帳追記を
        スキップし使用ログのみ記録する。残高更新・台帳・使用ログはすべて同一 commit で確定し、
        いずれか失敗時は全体を rollback する（課金済みなのに使用ログが無い、等の半端な状態を
        作らない / ADR-0012）。適用後残高を返す（無料モデルは None）。
        """
        balance_after: int | None = None
        try:
            if amount != 0:
                balance_after = self._stage_balance_change(
                    amount=amount,
                    transaction_type=transaction_type,
                    description=description,
                )
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
        except Exception:
            self.db.rollback()
            raise
        return balance_after

    def list_transactions(self, limit: int = 50) -> list[CreditTransaction]:
        """台帳履歴を新しい順に返す。"""
        stmt = (
            select(CreditTransaction)
            .where(CreditTransaction.user_id == self.user_id)
            .order_by(CreditTransaction.created_at.desc(), CreditTransaction.id)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def usage_summary(self) -> list[Row]:
        """使用ログをモデル別に集計し、(model_alias, chat_count, input/output tokens,
        credit_cost) の行を返す。利用実績のないモデルは行に現れない
        （表示側がモデル一覧の正本を持ち、0 件は表示側で補う / ADR-0012）。
        """
        stmt = (
            select(
                AgentUsageLog.model_alias.label("model_alias"),
                func.count().label("chat_count"),
                func.coalesce(func.sum(AgentUsageLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(AgentUsageLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(AgentUsageLog.credit_cost), 0).label("credit_cost"),
            )
            .where(AgentUsageLog.user_id == self.user_id)
            .group_by(AgentUsageLog.model_alias)
        )
        return list(self.db.execute(stmt).all())
