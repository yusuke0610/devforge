"""AI キャリア分析タスクのハンドラ。

libSQL (Hrana over HTTP) の idle stream timeout を避けるため、LLM 呼び出しの
前後でセッションを開閉する 3 フェーズ構成。
"""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ....core.logging_utils import get_logger
from ....models.career_analysis import CareerAnalysis
from ..exceptions import NonRetryableError
from .base import SessionFactory, TaskHandler

logger = get_logger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CareerAnalysisHandler(TaskHandler):
    """AI キャリアパス分析タスク。"""

    def get_record(self, db: Session, payload: dict) -> CareerAnalysis | None:
        user_id = payload.get("user_id")
        record_id = payload.get("record_id")
        if not user_id or not record_id:
            return None
        return db.query(CareerAnalysis).filter_by(id=record_id, user_id=user_id).first()

    async def run(self, session_factory: SessionFactory, payload: dict) -> None:
        from ...career_analysis.builder import (
            collect_career_inputs,
            generate_career_analysis,
        )
        from ...intelligence.llm import get_llm_client

        user_id = payload.get("user_id")
        record_id = payload.get("record_id")
        target_position = payload.get("target_position")
        # 必須キー欠落はディスパッチ側のバグであり、リトライしても回復しない。
        # ``dead_letter`` への遷移を worker に委ねるため NonRetryableError を raise する。
        missing = [
            name for name, value in (
                ("user_id", user_id),
                ("record_id", record_id),
                ("target_position", target_position),
            ) if not value
        ]
        if missing:
            message = "キャリア分析タスクのペイロードに必須キーがありません"
            logger.error(message, extra={"missing_keys": missing, "payload_keys": list(payload.keys())})
            raise NonRetryableError(f"{message} (missing={missing})")

        # ── フェーズA: 検証 + processing マーク + ユーザープロンプト生成 ─────
        with session_factory() as db:
            analysis = self.get_record(db, payload)
            if not analysis:
                message = "キャリア分析レコードが見つかりません"
                logger.error(message, extra={"record_id": record_id, "user_id": user_id})
                raise NonRetryableError(
                    f"{message} (record_id={record_id}, user_id={user_id})"
                )

            analysis.status = "processing"
            analysis.started_at = _now()
            db.commit()

            user_prompt = collect_career_inputs(db, user_id, target_position)

        # ── フェーズB: LLM 呼び出し（DB セッション無し）─────────────────────
        llm_client = get_llm_client()
        try:
            result = await generate_career_analysis(user_prompt, llm_client)
        except ValueError as exc:
            with session_factory() as db:
                analysis = self.get_record(db, payload)
                if analysis:
                    analysis.status = "dead_letter"
                    analysis.error_message = str(exc)
                    analysis.completed_at = _now()
                    db.commit()
            raise

        # ── フェーズC: 結果書き戻し（新セッション）───────────────────────────
        with session_factory() as db:
            analysis = self.get_record(db, payload)
            if not analysis:
                logger.warning(
                    "結果書き戻し時にレコードが見つかりません",
                    extra={"record_id": record_id, "user_id": user_id},
                )
                return
            analysis.result_json = json.dumps(result, ensure_ascii=False)
            analysis.status = "completed"
            analysis.error_message = None
            analysis.completed_at = _now()
            db.commit()
