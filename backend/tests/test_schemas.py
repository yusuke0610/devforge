import pytest
from app.schemas import (
    BlogSummaryRequest,
    Experience,
    Project,
    ResumeCreate,
)
from pydantic import ValidationError


def experience_payload() -> dict:
    return {
        "company": "Example株式会社",
        "business_description": "SES事業",
        "start_date": "2021-04",
        "end_date": "2024-03",
        "is_current": False,
        "employee_count": "300名",
        "capital": "1億円",
        "clients": [
            {
                "name": "クライアントA",
                "projects": [
                    {
                        "name": "API開発",
                        "role": "メンバー",
                        "description": "API開発",
                        "challenge": "課題",
                        "action": "行動",
                        "result": "処理速度を改善",
                        "team": {
                            "total": "5",
                            "members": [
                                {"role": "SE", "count": 3},
                                {"role": "PG", "count": 2},
                            ],
                        },
                        "technology_stacks": [{"category": "language", "name": "Python"}],
                    }
                ],
            }
        ],
    }


def test_current_experience_forces_end_date_none() -> None:
    payload = experience_payload()
    payload["is_current"] = True
    payload["end_date"] = "2024-03"

    experience = Experience(**payload)

    assert experience.end_date is None


def test_end_date_is_required_when_not_current() -> None:
    payload = experience_payload()
    payload["is_current"] = False
    payload["end_date"] = ""

    with pytest.raises(ValidationError):
        Experience(**payload)


def test_framework_category_is_accepted() -> None:
    payload = experience_payload()
    payload["clients"][0]["projects"][0]["technology_stacks"] = [
        {"category": "framework", "name": "FastAPI"}
    ]

    experience = Experience(**payload)

    assert experience.clients[0].projects[0].technology_stacks[0].category == "framework"


def test_unknown_category_is_rejected() -> None:
    payload = experience_payload()
    payload["clients"][0]["projects"][0]["technology_stacks"] = [
        {"category": "ミドルウェア", "name": "Nginx"}
    ]

    with pytest.raises(ValidationError):
        Experience(**payload)


def test_resume_requires_career_summary() -> None:
    payload = {
        "full_name": "山田 太郎",
        "self_pr": "自己PR",
        "experiences": [experience_payload()],
        "qualifications": [],
    }

    with pytest.raises(ValidationError):
        ResumeCreate(**payload)


def test_resume_requires_full_name() -> None:
    payload = {
        "career_summary": "要約",
        "self_pr": "自己PR",
        "experiences": [experience_payload()],
        "qualifications": [],
    }

    with pytest.raises(ValidationError):
        ResumeCreate(**payload)


def test_project_migrates_scale_to_team() -> None:
    """旧形式 scale → team に自動変換されることを検証する。"""
    proj = Project(
        **{
            "name": "テスト",
            "scale": "10",
            "technology_stacks": [],
        }
    )
    assert proj.team.total == "10"
    assert proj.team.members == []


def test_experience_end_date_before_start_date_is_rejected() -> None:
    """経歴: 終了日が開始日より前の場合は422エラーとなること。"""
    payload = experience_payload()
    payload["start_date"] = "2024-04"
    payload["end_date"] = "2021-03"
    payload["is_current"] = False

    with pytest.raises(ValidationError, match="開始日は終了日より前"):
        Experience(**payload)


def test_experience_end_date_equals_start_date_is_accepted() -> None:
    """経歴: 終了日 = 開始日は正常に保存されること。"""
    payload = experience_payload()
    payload["start_date"] = "2024-04"
    payload["end_date"] = "2024-04"
    payload["is_current"] = False

    exp = Experience(**payload)
    assert exp.start_date == "2024-04"
    assert exp.end_date == "2024-04"


def test_experience_end_date_after_start_date_is_accepted() -> None:
    """経歴: 終了日 > 開始日は正常に保存されること。"""
    payload = experience_payload()
    payload["start_date"] = "2021-04"
    payload["end_date"] = "2024-03"
    payload["is_current"] = False

    exp = Experience(**payload)
    assert exp.start_date == "2021-04"
    assert exp.end_date == "2024-03"


def test_experience_null_end_date_is_accepted() -> None:
    """経歴: 終了日がNULL（在職中）は正常に保存されること。"""
    payload = experience_payload()
    payload["is_current"] = True
    payload["end_date"] = "2024-03"

    exp = Experience(**payload)
    assert exp.end_date is None


def test_project_end_date_before_start_date_is_rejected() -> None:
    """プロジェクト: 終了日が開始日より前の場合はエラーとなること。"""
    with pytest.raises(ValidationError, match="開始日は終了日より前"):
        Project(
            name="テスト",
            start_date="2024-04",
            end_date="2021-03",
            is_current=False,
            technology_stacks=[],
        )


def test_project_end_date_equals_start_date_is_accepted() -> None:
    """プロジェクト: 終了日 = 開始日は正常に保存されること。"""
    proj = Project(
        name="テスト",
        start_date="2024-04",
        end_date="2024-04",
        is_current=False,
        technology_stacks=[],
    )
    assert proj.end_date == "2024-04"


def test_project_end_date_after_start_date_is_accepted() -> None:
    """プロジェクト: 終了日 > 開始日は正常に保存されること。"""
    proj = Project(
        name="テスト",
        start_date="2021-04",
        end_date="2024-03",
        is_current=False,
        technology_stacks=[],
    )
    assert proj.end_date == "2024-03"


def test_project_null_end_date_is_accepted() -> None:
    """プロジェクト: 参画中（is_current=True）は end_date 未指定または None を許容すること。

    DB 側は end_date が NULL で保存され、ResumeProject.end_date プロパティは None を返す。
    Experience.end_date と同様にスキーマも str | None を許容し、レスポンス検証が失敗しないようにする。
    """
    # 未指定（デフォルト）
    proj = Project(
        name="テスト",
        start_date="2021-04",
        is_current=True,
        technology_stacks=[],
    )
    assert proj.end_date is None

    # 明示的に None
    proj_none = Project(
        name="テスト",
        start_date="2021-04",
        end_date=None,
        is_current=True,
        technology_stacks=[],
    )
    assert proj_none.end_date is None

    # 空文字列も受け付け、is_current=True なら None に正規化する（Experience と同じ挙動）
    proj_empty = Project(
        name="テスト",
        start_date="2021-04",
        end_date="",
        is_current=True,
        technology_stacks=[],
    )
    assert proj_empty.end_date is None


def test_blog_summary_request_limits_article_count() -> None:
    article = {
        "platform": "zenn",
        "title": "記事タイトル",
        "url": "https://zenn.dev/example/articles/test",
        "published_at": "2026-03-19",
        "likes_count": 1,
        "summary": "概要",
        "tags": ["Python"],
    }

    with pytest.raises(ValidationError):
        BlogSummaryRequest(articles=[article] * 51)
