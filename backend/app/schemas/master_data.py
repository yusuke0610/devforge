"""マスタデータの Pydantic スキーマ。

FE 同期: ``MasterItem`` / ``TechStackMasterItem`` は
``frontend/src/types.ts`` の同名 type と対になる DTO。
言語境界のため codegen 未導入の手動同期で運用している（エラーコードの errors.py と同方針）。
フィールドを増減・rename する場合は対応する FE type も同時に更新すること。
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MasterItem(BaseModel):
    """マスタデータ共通レスポンス（資格など）。"""

    id: UUID
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class MasterItemCreate(BaseModel):
    """マスタデータ共通の作成リクエスト（資格など）。"""

    name: str = Field(min_length=1, max_length=200)
    sort_order: int = Field(default=0)


class MasterItemUpdate(BaseModel):
    """マスタデータ共通の更新リクエスト（資格など）。"""

    name: str = Field(min_length=1, max_length=200)
    sort_order: int = Field(default=0)


class TechStackMasterItem(BaseModel):
    """技術スタックマスタのレスポンス。"""

    id: UUID
    category: str
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class TechStackMasterCreate(BaseModel):
    """技術スタックマスタの作成リクエスト。"""

    category: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    sort_order: int = Field(default=0)


class TechStackMasterUpdate(BaseModel):
    """技術スタックマスタの更新リクエスト。"""

    category: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    sort_order: int = Field(default=0)
