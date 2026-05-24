"""ブログ AI サマリタスクのハンドラ。

libSQL (Hrana over HTTP) の idle stream timeout を避けるため、LLM 呼び出しの
前後でセッションを開閉する 3 フェーズ構成:

  - フェーズA: 入力検証 + processing マーク + 記事データの dict 化 (短命セッション)
  - フェーズB: LLM 呼び出し (DB セッション無し)
  - フェーズC: 結果書き戻し (新セッション)

フェーズ B 中はセッションを保持しないため、Hrana stream が失効しても影響しない。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ....core.logging_utils import get_logger
from ....models import BlogSummaryCache
from ....repositories import BlogArticleRepository
from ..exceptions import NonRetryableError
from .base import SessionFactory, TaskHandler

logger = get_logger(__name__)


# サマリ結果の保持期間（DB 取得時にこの期間を過ぎていれば破棄して再生成を促す）
_SUMMARY_TTL = timedelta(days=7)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class BlogSummarizeHandler(TaskHandler):
    """ブログ記事の AI サマリ生成タスク。"""

    def get_record(self, db: Session, payload: dict) -> BlogSummaryCache | None:
        user_id = payload.get("user_id")
        if not user_id:
            return None
        return db.query(BlogSummaryCache).filter_by(user_id=user_id).first()

    async def run(self, session_factory: SessionFactory, payload: dict) -> None:
        from ...intelligence.llm import get_llm_client
        from ...intelligence.llm_summarizer import summarize_blog_articles

        user_id = payload.get("user_id")
        if not user_id:
            message = "ペイロードに user_id がありません"
            logger.error(message, extra={"payload_keys": list(payload.keys())})
            raise NonRetryableError(f"{message} (payload_keys={list(payload.keys())})")

        # ── フェーズA: 検証 + processing マーク + 記事データ収集 ─────────────
        with session_factory() as db:
            cache = self.get_record(db, payload)
            if not cache:
                message = "ブログサマリキャッシュが見つかりません"
                logger.error(message, extra={"user_id": user_id})
                raise NonRetryableError(f"{message} (user_id={user_id})")

            cache.status = "processing"
            cache.started_at = _now()
            db.commit()

            # 記事は payload ではなく DB から取得する（GET /api/blog/articles と同じソース）。
            # LLM 前にローカル dict 化して、フェーズ B で DB セッションを持たない状態にする。
            article_rows = BlogArticleRepository(db, user_id).list_by_user()
            if not article_rows:
                cache.status = "dead_letter"
                cache.error_message = "分析対象の記事がありません"
                cache.completed_at = _now()
                db.commit()
                return

            articles_data = [
                {
                    "title": art.title,
                    "url": art.url,
                    "published_at": art.published_at,
                    "likes_count": art.likes_count,
                    "summary": art.summary,
                    "tags": art.tags,
                    "platform": art.platform,
                }
                for art in article_rows
            ]

        # ── フェーズB: LLM 呼び出し（DB セッション無し）─────────────────────
        llm_client = get_llm_client()
        if not await llm_client.check_available():
            with session_factory() as db:
                cache = self.get_record(db, payload)
                if cache:
                    cache.status = "dead_letter"
                    cache.error_message = "LLM サービスが利用できません"
                    cache.completed_at = _now()
                    db.commit()
            return

        summary = await summarize_blog_articles(articles_data)

        # ── フェーズC: 結果書き戻し（新セッション）───────────────────────────
        with session_factory() as db:
            cache = self.get_record(db, payload)
            if not cache:
                # レコード消失は外部要因（手動削除など）であり、ここでは何もしない
                logger.warning(
                    "結果書き戻し時にレコードが見つかりません",
                    extra={"user_id": user_id},
                )
                return

            if not summary:
                cache.status = "dead_letter"
                cache.error_message = "要約の生成に失敗しました"
                cache.completed_at = _now()
                db.commit()
                return

            cache.summary = summary
            cache.status = "completed"
            cache.error_message = None
            cache.completed_at = _now()
            cache.expires_at = _now() + _SUMMARY_TTL
            db.commit()
