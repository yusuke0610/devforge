"""職務経歴書 PDF インポート（割り当て候補ブロック抽出）の API スキーマ。"""

from pydantic import BaseModel


class ResumeImportBlock(BaseModel):
    """インポート補助 UI に並べる割り当て候補ブロック。"""

    id: int
    kind: str  # "line"（本文行）| "table"（表セル）
    text: str


class ResumeImportBlocksResponse(BaseModel):
    """POST /api/resumes/import/extract のレスポンス（同期・LLM 不使用）。"""

    blocks: list[ResumeImportBlock]
