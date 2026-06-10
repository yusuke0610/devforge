from app.services.markdown.generators.resume_generator import build_resume_markdown


def _payload(capital: str, capital_unit: str | None) -> dict:
    exp: dict = {
        "company": "Example株式会社",
        "business_description": "SES事業",
        "start_date": "2021-04",
        "end_date": "2024-03",
        "is_current": False,
        "capital": capital,
        "clients": [],
    }
    if capital_unit is not None:
        exp["capital_unit"] = capital_unit
    return {
        "full_name": "山田 太郎",
        "career_summary": "職務要約",
        "self_pr": "自己PR",
        "qualifications": [],
        "experiences": [exp],
    }


def test_capital_unit_reflected_in_markdown() -> None:
    md = build_resume_markdown(_payload("5", "百万円"))
    assert "5百万円" in md
    assert "千万円" not in md


def test_capital_unit_defaults_to_sen_man_when_missing() -> None:
    # capital_unit を持たない旧データは後方互換で「千万円」表示になる。
    md = build_resume_markdown(_payload("5", None))
    assert "5千万円" in md


def test_contact_fields_rendered_when_present() -> None:
    md = build_resume_markdown(
        {
            "full_name": "山田 太郎",
            "email": "yamada@example.com",
            "github_url": "https://github.com/yamada",
            "career_summary": "職務要約",
            "self_pr": "自己PR",
            "qualifications": [],
            "experiences": [],
        }
    )
    assert "yamada@example.com" in md
    # ラベルは email / github（小文字）。
    assert "**email:**" in md
    assert "**github:**" in md
    # github URL は Markdown リンク記法でハイパーリンク化する。
    assert "[https://github.com/yamada](https://github.com/yamada)" in md


def test_contact_fields_omitted_when_empty() -> None:
    # github URL は任意。空なら github 行を出さない（email は必須運用だが空入力にも耐える）。
    md = build_resume_markdown(
        {
            "full_name": "山田 太郎",
            "email": "yamada@example.com",
            "github_url": "",
            "career_summary": "職務要約",
            "self_pr": "自己PR",
            "qualifications": [],
            "experiences": [],
        }
    )
    assert "**github:**" not in md


def _it_experience() -> dict:
    return {
        "company": "Example株式会社",
        "business_description": "SES事業",
        "start_date": "2019-04",
        "end_date": "2024-03",
        "is_current": False,
        "is_it_company": True,
        "clients": [
            {
                "name": "顧客A",
                "has_client": True,
                "is_vacation": False,
                "projects": [
                    {
                        "name": "API開発",
                        "periods": [
                            {"start_date": "2021-04", "end_date": "2024-03", "is_current": False}
                        ],
                        "role": "SE",
                        "description": "性能改善を担当",
                        "technology_stacks": [{"category": "language", "name": "Python"}],
                    }
                ],
            }
        ],
    }


def test_non_it_experience_renders_description_without_project_table() -> None:
    """非IT経歴は詳細を出力し、取引先/プロジェクト見出しを出さない。"""
    payload = {
        "full_name": "佐藤 花子",
        "career_summary": "要約",
        "self_pr": "自己PR",
        "qualifications": [],
        "experiences": [
            {
                "company": "〇〇商事",
                "business_description": "小売業",
                "start_date": "2016-04",
                "end_date": "2019-03",
                "is_current": False,
                "is_it_company": False,
                "description": "店舗運営・在庫管理を担当",
                "clients": [],
            }
        ],
    }

    md = build_resume_markdown(payload)

    assert "店舗運営・在庫管理を担当" in md
    # 非IT経歴では取引先見出し（####）やプロジェクト見出し（#####）を出さない。
    assert "####" not in md


def test_vacation_client_renders_period_and_detail() -> None:
    """休暇エントリは期間と詳細を出力する。"""
    exp = _it_experience()
    exp["clients"] = [
        {
            "is_vacation": True,
            "vacation_start_date": "2020-04",
            "vacation_end_date": "2021-03",
            "vacation_is_current": False,
            "vacation_description": "育児休暇を取得",
        }
    ]
    payload = {
        "full_name": "佐藤 花子",
        "career_summary": "要約",
        "self_pr": "自己PR",
        "qualifications": [],
        "experiences": [exp],
    }

    md = build_resume_markdown(payload)

    assert "#### 休暇" in md
    assert "2020-04 - 2021-03" in md
    assert "育児休暇を取得" in md


def test_it_experience_renders_projects_unchanged() -> None:
    """既存のIT経路は取引先・プロジェクトを従来どおり出力する。"""
    payload = {
        "full_name": "山田 太郎",
        "career_summary": "要約",
        "self_pr": "自己PR",
        "qualifications": [],
        "experiences": [_it_experience()],
    }

    md = build_resume_markdown(payload)

    assert "#### 顧客A" in md
    assert "##### API開発" in md
    assert "性能改善を担当" in md
