"""職務経歴書 PDF インポートタスクのハンドラ。"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ....models.resume_import import ResumeImport
from ..exceptions import NonRetryableError
from .base import TaskHandler

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ResumeImportHandler(TaskHandler):
    """PDF を pdfplumber でテキスト抽出し LLM で構造化するタスク。"""

    def get_record(self, db: Session, payload: dict) -> ResumeImport | None:
        user_id = payload.get("user_id")
        import_id = payload.get("import_id")
        if not user_id or not import_id:
            return None
        return db.query(ResumeImport).filter_by(id=import_id, user_id=user_id).first()

    async def run(self, db: Session, payload: dict) -> None:
        from ....services.intelligence.llm import get_llm_client
        from ....services.resume_import import llm_extractor, pdf_extractor

        user_id = payload.get("user_id")
        import_id = payload.get("import_id")
        missing = [name for name, v in (("user_id", user_id), ("import_id", import_id)) if not v]
        if missing:
            message = "インポートタスクのペイロードに必須キーがありません"
            logger.error(message, extra={"missing_keys": missing})
            raise NonRetryableError(f"{message} (missing={missing})")

        record = db.query(ResumeImport).filter_by(id=import_id, user_id=user_id).first()
        if not record:
            message = "ResumeImport レコードが見つかりません"
            logger.error(message, extra={"import_id": import_id, "user_id": user_id})
            raise NonRetryableError(f"{message} (import_id={import_id})")

        record.status = "processing"
        record.started_at = _now()
        db.commit()

        pdf_bytes = record.pdf_blob
        if not pdf_bytes:
            record.error_message = "PDF データが見つかりません"
            record.status = "dead_letter"
            record.completed_at = _now()
            db.commit()
            raise NonRetryableError("PDF データが見つかりません")

        # テキスト抽出
        extracted = pdf_extractor.extract_text(pdf_bytes)
        if not extracted.has_text_layer:
            record.is_resume_flag = False
            record.judge_reason = "テキストレイヤーのない PDF です"
            record.error_message = "スキャン PDF のためテキスト抽出不可"
            record.pdf_blob = None
            record.completed_at = _now()
            db.commit()
            raise NonRetryableError("スキャン PDF のためテキスト抽出不可")

        llm_client = get_llm_client()

        # LLM による職務経歴書判定
        judge_result = await llm_extractor.judge_is_resume(extracted.text, llm_client)
        if not judge_result.is_resume:
            record.is_resume_flag = False
            record.judge_reason = judge_result.reason
            record.error_message = f"not_a_resume: {judge_result.reason}"
            record.pdf_blob = None
            record.completed_at = _now()
            db.commit()
            raise NonRetryableError(f"not_a_resume: {judge_result.reason}")

        # 構造化抽出
        structured = await llm_extractor.extract_structured(extracted.text, llm_client)

        record.result_json = json.dumps(structured, ensure_ascii=False)
        record.is_resume_flag = True
        record.judge_reason = judge_result.reason
        record.pdf_blob = None
        record.status = "completed"
        record.error_message = None
        record.completed_at = _now()
        db.commit()
