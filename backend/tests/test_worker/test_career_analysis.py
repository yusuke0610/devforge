"""_run_career_analysis と _mark_dead_letter (career_analysis) の単体テスト。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.models.career_analysis import CareerAnalysis
from app.repositories import UserRepository
from app.services.tasks.base import TaskType
from app.services.tasks.worker import (
    _mark_dead_letter,
    _run_career_analysis,
)
from sqlalchemy.orm import Session

from ._helpers import run_sync as _run


class TestRunCareerAnalysis:
    def _make_user_and_analysis(self, db: Session, username="career-worker-user"):
        user = UserRepository(db).create(
            username,
            hashed_password=None,
            email=f"{username}@test.com",
        )
        analysis = CareerAnalysis(
            user_id=user.id,
            version=1,
            target_position="バックエンドエンジニア",
            status="pending",
        )
        db.add(analysis)
        db.commit()
        return user, analysis

    def test_success_status_completed(self, db_session: Session, session_factory):
        """正常系: キャリア分析が完了し status が completed になること。"""
        user, analysis = self._make_user_and_analysis(db_session)
        mock_llm = MagicMock()
        fake_result = {"strengths": [], "career_paths": [], "action_items": []}

        # ハンドラは collect_career_inputs + generate_career_analysis を分けて呼ぶ。
        # ここでは LLM 部分の generate_career_analysis をモックする。
        with (
            patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm),
            patch(
                "app.services.career_analysis.builder.generate_career_analysis",
                new_callable=AsyncMock,
                return_value=fake_result,
            ),
        ):
            _run(
                _run_career_analysis(
                    session_factory,
                    {
                        "user_id": user.id,
                        "record_id": analysis.id,
                        "target_position": "バックエンドエンジニア",
                    },
                )
            )

        db_session.refresh(analysis)
        assert analysis.status == "completed"
        assert analysis.result_json is not None
        assert analysis.completed_at is not None

    def test_value_error_sets_dead_letter(self, db_session: Session, session_factory):
        """generate_career_analysis が ValueError を送出した場合 status が dead_letter になること。"""
        user, analysis = self._make_user_and_analysis(db_session, "career-err")
        mock_llm = MagicMock()

        with (
            patch("app.services.intelligence.llm.get_llm_client", return_value=mock_llm),
            patch(
                "app.services.career_analysis.builder.generate_career_analysis",
                new_callable=AsyncMock,
                side_effect=ValueError("必要なデータが不足しています"),
            ),
        ):
            with pytest.raises(ValueError):
                _run(
                    _run_career_analysis(
                        session_factory,
                        {
                            "user_id": user.id,
                            "record_id": analysis.id,
                            "target_position": "バックエンドエンジニア",
                        },
                    )
                )

        db_session.refresh(analysis)
        assert analysis.status == "dead_letter"
        assert analysis.error_message is not None
        assert "不足" in analysis.error_message

    def test_no_record_raises_non_retryable(self, session_factory):
        """レコードが見つからない場合、NonRetryableError が送出されること。

        旧契約（silent return）は worker から completed と誤って観測される回帰を招くため、
        ``dead_letter`` への遷移を強制する。
        """
        from app.services.tasks.exceptions import NonRetryableError

        with pytest.raises(NonRetryableError):
            _run(
                _run_career_analysis(
                    session_factory,
                    {
                        "user_id": "ghost",
                        "record_id": 99999,
                        "target_position": "test",
                    },
                )
            )


class TestMarkDeadLetterCareerAnalysis:
    def test_mark_dead_letter_career_analysis(self, db_session: Session):
        """_mark_dead_letter が CareerAnalysis のステータスを dead_letter に更新すること。"""
        user = UserRepository(db_session).create(
            "mf-career-user", hashed_password=None, email="mfcareer@test.com"
        )
        analysis = CareerAnalysis(
            user_id=user.id,
            version=1,
            target_position="SRE",
            status="processing",
        )
        db_session.add(analysis)
        db_session.commit()

        _mark_dead_letter(
            db_session,
            TaskType.CAREER_ANALYSIS,
            {"user_id": user.id, "record_id": analysis.id},
        )

        db_session.refresh(analysis)
        assert analysis.status == "dead_letter"
        assert analysis.error_message == "予期しないエラーが発生しました"

    def test_mark_dead_letter_does_not_overwrite_completed(self, db_session: Session):
        """completed 済みのレコードは _mark_dead_letter で上書きされないこと。"""
        user = UserRepository(db_session).create(
            "mf-career-done", hashed_password=None, email="mfcareerdone@test.com"
        )
        analysis = CareerAnalysis(
            user_id=user.id,
            version=1,
            target_position="SRE",
            status="completed",
        )
        db_session.add(analysis)
        db_session.commit()

        _mark_dead_letter(
            db_session,
            TaskType.CAREER_ANALYSIS,
            {"user_id": user.id, "record_id": analysis.id},
        )

        db_session.refresh(analysis)
        assert analysis.status == "completed"
