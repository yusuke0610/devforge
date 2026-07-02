from sqlalchemy import select

from ..models import MQualification, MTechnologyStack
from .base import BaseMasterRepository


class MQualificationRepository(BaseMasterRepository):
    """資格マスタリポジトリ。"""

    _model = MQualification


class MTechnologyStackRepository(BaseMasterRepository):
    """技術スタックマスタリポジトリ。category フィールドを追加で管理する。"""

    _model = MTechnologyStack

    def list_by_category(self, category: str) -> list[MTechnologyStack]:
        statement = (
            select(MTechnologyStack)
            .where(MTechnologyStack.category == category)
            .order_by(MTechnologyStack.sort_order, MTechnologyStack.name)
        )
        return list(self.db.scalars(statement).all())

    # category 列を持つため基底の create/update をあえて拡張シグネチャで上書きする。
    # MTechnologyStackRepository 型で直接呼ぶ箇所のみが使い、基底経由の多態呼び出しは無いため
    # Liskov 非互換は意図的（reportIncompatibleMethodOverride を局所抑制）。
    def create(self, category: str, name: str, sort_order: int = 0) -> MTechnologyStack:  # pyright: ignore[reportIncompatibleMethodOverride]
        item = MTechnologyStack(category=category, name=name, sort_order=sort_order)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def update(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, item_id: str, category: str, name: str, sort_order: int = 0
    ) -> MTechnologyStack | None:
        item = self.db.scalar(select(MTechnologyStack).where(MTechnologyStack.id == item_id))
        if not item:
            return None
        item.category = category
        item.name = name
        item.sort_order = sort_order
        self.db.commit()
        self.db.refresh(item)
        return item
