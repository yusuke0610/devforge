"""職務経歴書 PDF インポートタスクのハンドラ。

libSQL (Hrana over HTTP) の idle stream timeout を避けるため、LLM 呼び出しの
前後でセッションを開閉する 3 フェーズ構成:

  - フェーズA: 検証 + processing マーク + pdf_blob のローカル取り込み (短命セッション)
  - フェーズB: PDF 抽出 + LLM judge + LLM extract (DB セッション無し)
  - フェーズC: 結果書き戻し (新セッション)

各フェーズ間で必要に応じて新セッションを開き、dead_letter マーク用の commit も
新セッションで行う。
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ....models.resume_import import ResumeImport
from ...progress_service import set_progress
from ..exceptions import NonRetryableError
from .base import SessionFactory, TaskHandler

logger = logging.getLogger(__name__)

# resume_import タスクの全体ステップ数。フロントの進捗バーで分母として使う。
_TOTAL_STEPS = 3


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

    async def run(self, session_factory: SessionFactory, payload: dict) -> None:
        from ....services.intelligence.llm import get_llm_client
        from ....services.resume_import import llm_extractor, pdf_extractor

        user_id = payload.get("user_id")
        import_id = payload.get("import_id")
        missing = [name for name, v in (("user_id", user_id), ("import_id", import_id)) if not v]
        if missing:
            message = "インポートタスクのペイロードに必須キーがありません"
            logger.error(message, extra={"missing_keys": missing})
            raise NonRetryableError(f"{message} (missing={missing})")

        # ── フェーズA: 検証 + processing マーク + pdf_blob 取り込み ───────────
        with session_factory() as db:
            record = self.get_record(db, payload)
            if not record:
                message = "ResumeImport レコードが見つかりません"
                logger.error(message, extra={"import_id": import_id, "user_id": user_id})
                raise NonRetryableError(f"{message} (import_id={import_id})")

            # pdf_blob は LLM 前にローカル変数へ取り込んでセッションを離す。
            pdf_bytes = record.pdf_blob

            record.status = "processing"
            record.started_at = _now()
            db.commit()

        if not pdf_bytes:
            with session_factory() as db:
                record = self.get_record(db, payload)
                if record:
                    record.error_message = "PDF データが見つかりません"
                    record.status = "dead_letter"
                    record.completed_at = _now()
                    db.commit()
            raise NonRetryableError("PDF データが見つかりません")

        # ── フェーズB: PDF 抽出 + LLM judge + LLM extract（DB セッション無し）─
        # 進捗バーの task_id は import_id を使う（user 単位だと並行 import を区別できないため）
        task_id = import_id

        # ステップ 1: PDF テキスト抽出
        await set_progress(task_id, 1, _TOTAL_STEPS, "PDFテキスト抽出中...")
        extracted = pdf_extractor.extract_text(pdf_bytes)
        if not extracted.has_text_layer:
            with session_factory() as db:
                record = self.get_record(db, payload)
                if record:
                    record.is_resume_flag = False
                    record.judge_reason = "テキストレイヤーのない PDF です"
                    record.error_message = "スキャン PDF のためテキスト抽出不可"
                    record.pdf_blob = None
                    record.status = "dead_letter"
                    record.completed_at = _now()
                    db.commit()
            raise NonRetryableError("スキャン PDF のためテキスト抽出不可")

        llm_client = get_llm_client()

        # ステップ 2: LLM による職務経歴書判定
        await set_progress(task_id, 2, _TOTAL_STEPS, "職務経歴書か判定中...")
        judge_result = await llm_extractor.judge_is_resume(extracted.text, llm_client)
        if not judge_result.is_resume:
            with session_factory() as db:
                record = self.get_record(db, payload)
                if record:
                    record.is_resume_flag = False
                    record.judge_reason = judge_result.reason
                    record.error_message = f"not_a_resume: {judge_result.reason}"
                    record.pdf_blob = None
                    record.status = "dead_letter"
                    record.completed_at = _now()
                    db.commit()
            raise NonRetryableError(f"not_a_resume: {judge_result.reason}")

        # ステップ 3: 構造化抽出
        await set_progress(task_id, 3, _TOTAL_STEPS, "構造化抽出中...")
        structured = await llm_extractor.extract_structured(extracted.text, llm_client)

        # ── フェーズC: 結果書き戻し（新セッション）───────────────────────────
        with session_factory() as db:
            record = self.get_record(db, payload)
            if not record:
                logger.warning(
                    "結果書き戻し時にレコードが見つかりません",
                    extra={"import_id": import_id, "user_id": user_id},
                )
                return
            record.result_json = json.dumps(structured, ensure_ascii=False)
            record.is_resume_flag = True
            record.judge_reason = judge_result.reason
            record.pdf_blob = None
            record.status = "completed"
            record.error_message = None
            record.completed_at = _now()
            db.commit()

        # 完了マーカー（フロントは step_index >= total_steps で done スタイルに切り替わる）
        await set_progress(task_id, _TOTAL_STEPS, _TOTAL_STEPS, "完了")
