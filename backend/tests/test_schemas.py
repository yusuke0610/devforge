import pytest
from app.schemas import (
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
                        "start_date": "2021-04",
                        "end_date": "2024-03",
                        "is_current": False,
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


def test_current_experience_forces_end_date_empty() -> None:
    """在籍中（is_current=True）なら end_date は "" に正規化される。"""
    payload = experience_payload()
    payload["is_current"] = True
    payload["end_date"] = "2024-03"

    experience = Experience(**payload)

    assert experience.end_date == ""


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
            "start_date": "2021-04",
            "end_date": "2024-03",
            "scale": "10",
            "technology_stacks": [],
        }
    )
    assert proj.team.total == "10"
    assert proj.team.members == []


def test_project_requires_start_date() -> None:
    """プロジェクト: 案件名があっても開始年月が空なら 422（日本語メッセージ）。

    旧実装ではここを素通りし、repositories 層の parse_year_month("") で 500 になっていた。
    """
    with pytest.raises(ValidationError, match="開始年月を入力してください"):
        Project(
            name="API開発",
            start_date="",
            end_date="2024-03",
            is_current=False,
            technology_stacks=[],
        )


def test_project_requires_end_date_when_not_current() -> None:
    """プロジェクト: 参画中でなければ終了年月が必須。"""
    with pytest.raises(ValidationError, match="終了年月"):
        Project(
            name="API開発",
            start_date="2021-04",
            end_date="",
            is_current=False,
            technology_stacks=[],
        )


def test_project_current_without_end_date_is_accepted() -> None:
    """プロジェクト: 参画中（is_current=True）なら終了年月が空でも OK。"""
    proj = Project(
        name="API開発",
        start_date="2021-04",
        end_date="",
        is_current=True,
        technology_stacks=[],
    )
    assert proj.start_date == "2021-04"
    assert proj.end_date == ""


def test_experience_requires_start_date_with_japanese_message() -> None:
    """経歴: 会社名があっても開始年月が空なら 422（日本語メッセージ）。"""
    payload = experience_payload()
    payload["start_date"] = ""

    with pytest.raises(ValidationError, match="開始年月を入力してください"):
        Experience(**payload)


def test_experience_allows_empty_employee_count_and_capital() -> None:
    """経歴: 会社名・在籍期間があれば従業員数・資本金は空でも保存できる（任意入力）。"""
    payload = experience_payload()
    payload["employee_count"] = ""
    payload["capital"] = ""

    exp = Experience(**payload)
    assert exp.employee_count == ""
    assert exp.capital == ""


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


def test_experience_in_progress_end_date_is_normalized_to_empty() -> None:
    """経歴: 在職中（is_current=True）は end_date が "" に正規化されること。

    schema 上は str 必須・None 不可。在籍中なら値が入っていても "" に丸める。
    """
    payload = experience_payload()
    payload["is_current"] = True
    payload["end_date"] = "2024-03"

    exp = Experience(**payload)
    assert exp.end_date == ""


def test_experience_end_date_none_is_rejected() -> None:
    """経歴: end_date に None を渡すと ValidationError になる（str 必須契約）。"""
    payload = experience_payload()
    payload["is_current"] = True
    payload["end_date"] = None

    with pytest.raises(ValidationError):
        Experience(**payload)


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


def test_project_in_progress_end_date_is_normalized_to_empty() -> None:
    """プロジェクト: 参画中（is_current=True）は end_date が "" に正規化されること。

    DB 側は end_date が NULL で保存され、ResumeProject.end_date プロパティは "" を返す。
    Experience.end_date と同じ契約で、schema は str 必須・None 不可。
    """
    # 未指定（デフォルト ""）
    proj = Project(
        name="テスト",
        start_date="2021-04",
        is_current=True,
        technology_stacks=[],
    )
    assert proj.end_date == ""

    # 値が入っていても is_current=True なら "" に正規化される
    proj_overridden = Project(
        name="テスト",
        start_date="2021-04",
        end_date="2024-03",
        is_current=True,
        technology_stacks=[],
    )
    assert proj_overridden.end_date == ""

    # 空文字列も当然 OK
    proj_empty = Project(
        name="テスト",
        start_date="2021-04",
        end_date="",
        is_current=True,
        technology_stacks=[],
    )
    assert proj_empty.end_date == ""


def test_project_end_date_none_is_rejected() -> None:
    """プロジェクト: end_date に None を渡すと ValidationError になる。"""
    with pytest.raises(ValidationError):
        Project(
            name="テスト",
            start_date="2021-04",
            end_date=None,
            is_current=True,
            technology_stacks=[],
        )
