"""
ブログ連携 API ルーターパッケージ。

責務別にサブモジュールへ分割している。
- accounts: 連携アカウント CRUD と記事一覧
- sync:     外部 API からの手動同期
- score:    ブログスコアリング
"""

from fastapi import APIRouter

from . import accounts, score, sync

router = APIRouter(prefix="/api/blog", tags=["blog"])
router.include_router(accounts.router)
router.include_router(sync.router)
router.include_router(score.router)

__all__ = ["router"]
