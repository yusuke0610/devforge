import base64

from app.services.pdf.generators.resume_generator import (
    _build_html,
    build_resume_pdf,
)
from app.services.pdf.utils.pdf_utils import (
    decode_photo as _decode_photo,
)
from app.services.pdf.utils.pdf_utils import (
    format_period as _format_period,
)
from app.services.pdf.utils.pdf_utils import (
    parse_date_ym as _parse_date_ym,
)


def test_format_period_for_current() -> None:
    period = _format_period("2022-04", None, True)
    assert "現在" in period


def test_build_resume_pdf_returns_pdf_bytes() -> None:
    payload = {
        "full_name": "山田 太郎",
        "qualifications": [{"acquired_date": "2020-04-01", "name": "応用情報技術者"}],
        "career_summary": "職務要約テスト",
        "self_pr": "自己PRテスト",
        "experiences": [],
    }

    pdf_bytes = build_resume_pdf(payload)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 100


def test_build_resume_pdf_with_non_it_and_vacation() -> None:
    """非IT経歴と休暇エントリを含む payload でも PDF を生成できる。"""
    payload = {
        "full_name": "佐藤 花子",
        "qualifications": [],
        "career_summary": "職務要約",
        "self_pr": "自己PR",
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
            },
            {
                "company": "Example株式会社",
                "business_description": "SES事業",
                "start_date": "2019-04",
                "end_date": "2024-03",
                "is_current": False,
                "is_it_company": True,
                "clients": [
                    {
                        "is_vacation": True,
                        "vacation_start_date": "2020-04",
                        "vacation_end_date": "2021-03",
                        "vacation_is_current": False,
                        "vacation_description": "育児休暇を取得",
                    }
                ],
            },
        ],
    }

    pdf_bytes = build_resume_pdf(payload)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 100


def test_build_html_annotates_data_fp() -> None:
    """_build_html が careerDiff のパスと一致する data-fp を各値ノードに付与する。"""
    payload = {
        "full_name": "山田太郎",
        "career_summary": "要約",
        "self_pr": "PR",
        "qualifications": [{"acquired_date": "2020-04", "name": "応用情報技術者"}],
        "experiences": [
            {
                "company": "Example株式会社",
                "business_description": "SES事業",
                "start_date": "2020-04",
                "end_date": "2024-03",
                "is_current": False,
                "is_it_company": True,
                "clients": [
                    {
                        "name": "取引先A",
                        "has_client": True,
                        "projects": [
                            {
                                "name": "案件X",
                                "role": "SE",
                                "periods": [
                                    {"start_date": "2020-04", "end_date": "2021-03"}
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    html = _build_html(payload)

    assert 'data-fp="full_name"' in html
    assert 'data-fp="career_summary"' in html
    assert 'data-fp="self_pr"' in html
    assert 'data-fp="experiences.0.company"' in html
    assert 'data-fp="experiences.0.business_description"' in html
    # 期間はフィールド単位の span に分割し、start_date / end_date を個別に紐づける
    # （end_date / is_current の編集も左右 diff でハイライトできるようにするため）
    assert 'data-fp="experiences.0.start_date"' in html
    assert 'data-fp="experiences.0.end_date"' in html
    assert 'data-fp="experiences.0.clients.0.name"' in html
    assert 'data-fp="experiences.0.clients.0.projects.0.role"' in html
    assert 'data-fp="experiences.0.clients.0.projects.0.periods"' in html
    assert 'data-fp="experiences.0.clients.0.projects.0.technology_stacks"' in html
    assert 'data-fp="qualifications.0.name"' in html
    # 折りたたみ用の項目コンテナ（data-unit）も付与される
    assert 'data-unit="experiences.0"' in html
    assert 'data-unit="experiences.0.clients.0.projects.0"' in html
    assert 'data-unit="qualifications.0"' in html


def test_project_structured_info_in_header_cell() -> None:
    """プロジェクトの構造化情報（期間/名前・役割/体制・工程）は左列見出しセルに集約され、
    独立ヘッダー（project-header）や「業務内容」ラベルは出力されない。description 本文は残る。"""
    payload = {
        "full_name": "山田太郎",
        "career_summary": "要約",
        "self_pr": "PR",
        "qualifications": [],
        "experiences": [
            {
                "company": "Example株式会社",
                "business_description": "SES事業",
                "start_date": "2020-04",
                "end_date": "2024-03",
                "is_current": False,
                "is_it_company": True,
                "clients": [
                    {
                        "name": "取引先A",
                        "has_client": True,
                        "projects": [
                            {
                                "name": "案件X",
                                "role": "メンバ",
                                "periods": [
                                    {"start_date": "2025-09", "end_date": "2026-12"}
                                ],
                                "team": {
                                    "total": "13",
                                    "members": [{"role": "PM", "count": 1}],
                                },
                                "phases": ["開発", "単体テスト", "総合テスト"],
                                "description": "サービス概要の説明文",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    html = _build_html(payload)

    # 構造化情報は左列見出しセル（th.proj-info）に入る
    assert 'class="proj-info"' in html
    # 見出し行は thead に置かない（thead だと WeasyPrint がページ跨ぎ時に
    # 各ページ先頭で見出しを繰り返すため）。tbody の通常行に置く。
    assert "<thead>" not in html
    # 旧来の独立ヘッダーと「業務内容」ラベルは廃止
    assert "project-header" not in html
    assert "<th>業務内容</th>" not in html
    # 役割・体制・工程・期間が見出しに含まれる
    assert "工程：" in html
    assert "体制：" in html
    assert "役割：" in html
    # description 本文は左列の本文セルに残る
    assert "サービス概要の説明文" in html
    assert 'data-fp="experiences.0.clients.0.projects.0.description"' in html


def test_build_html_renders_contact_fields() -> None:
    """メール・GitHub URL は値があるとき data-fp 付きで出力され、空なら省略される。"""
    html = _build_html(
        {
            "full_name": "山田太郎",
            "email": "yamada@example.com",
            "github_url": "https://github.com/yamada",
            "career_summary": "要約",
            "self_pr": "PR",
            "qualifications": [],
            "experiences": [],
        }
    )
    assert 'data-fp="email"' in html
    assert "yamada@example.com" in html
    # ラベルは email / github（小文字）で出す。
    assert "email　" in html
    assert "github　" in html
    assert 'data-fp="github_url"' in html
    assert "https://github.com/yamada" in html
    # github URL はハイパーリンク（青・下線）として <a class="meta-link" href=...> で出す。
    assert '<a class="meta-link" href="https://github.com/yamada"' in html

    # GitHub URL は任意。空なら github_url ノードを出さない。
    html_no_github = _build_html(
        {
            "full_name": "山田太郎",
            "email": "yamada@example.com",
            "github_url": "",
            "career_summary": "要約",
            "self_pr": "PR",
            "qualifications": [],
            "experiences": [],
        }
    )
    assert 'data-fp="github_url"' not in html_no_github


def test_build_html_period_binds_is_current() -> None:
    """在職中の期間は「現在」を is_current に、休暇期間は各日付フィールドに紐づける。"""
    payload = {
        "full_name": "山田太郎",
        "career_summary": "要約",
        "self_pr": "PR",
        "qualifications": [],
        "experiences": [
            {
                "company": "Example株式会社",
                "business_description": "SES事業",
                "start_date": "2020-04",
                "end_date": "",
                "is_current": True,
                "is_it_company": True,
                "clients": [
                    {
                        "name": "取引先A",
                        "has_client": True,
                        "is_vacation": True,
                        "vacation_start_date": "2021-01",
                        "vacation_end_date": "2021-03",
                        "vacation_is_current": False,
                        "vacation_description": "休養",
                    }
                ],
            }
        ],
    }

    html = _build_html(payload)

    # 在職中: 「現在」テキストは is_current に紐づく
    assert 'data-fp="experiences.0.is_current">現在</span>' in html
    # 休暇期間も start/end が個別の span になる
    assert 'data-fp="experiences.0.clients.0.vacation_start_date"' in html
    assert 'data-fp="experiences.0.clients.0.vacation_end_date"' in html


def test_build_resume_pdf_still_works_with_annotations() -> None:
    """data-fp 付与後も PDF 生成は従来どおり成功する（属性はレイアウトに影響しない）。"""
    payload = {
        "full_name": "山田太郎",
        "career_summary": "要約",
        "self_pr": "PR",
        "qualifications": [],
        "experiences": [
            {
                "company": "Example株式会社",
                "business_description": "SES事業",
                "start_date": "2020-04",
                "end_date": "2024-03",
                "is_current": False,
                "is_it_company": True,
                "clients": [
                    {
                        "name": "取引先A",
                        "has_client": True,
                        "projects": [
                            {
                                "name": "案件X",
                                "role": "SE",
                                "periods": [
                                    {"start_date": "2020-04", "end_date": "2021-03"}
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    pdf_bytes = build_resume_pdf(payload)
    assert pdf_bytes.startswith(b"%PDF")


def test_parse_date_ym() -> None:
    assert _parse_date_ym("2020-04") == ("2020", "4")
    assert _parse_date_ym("2020-12-01") == ("2020", "12")
    assert _parse_date_ym("") == ("", "")
    assert _parse_date_ym("invalid") == ("", "")


def test_decode_photo_valid() -> None:
    # 1x1 red PNG
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
        b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode()
    result = _decode_photo(data_url)
    assert result is not None
    assert result.read()[:4] == b"\x89PNG"


def test_decode_photo_none() -> None:
    assert _decode_photo(None) is None
    assert _decode_photo("") is None
    assert _decode_photo("not-a-data-url") is None
