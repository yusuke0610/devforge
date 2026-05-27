import pytest
from fastapi.testclient import TestClient

from conftest import auth_header

# ── CRUD: Auth required (401 without token) ────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/resumes"),
        ("get", "/api/resumes/latest"),
    ],
)
def test_endpoints_require_auth(client: TestClient, method: str, path: str) -> None:
    resp = getattr(client, method)(path)
    # POST は CSRF チェックが先行して 403、GET は認証チェックで 401 が返る
    assert resp.status_code in (401, 403)


# ── CRUD: Resume ────────────────────────────────────────────────


def test_resume_crud(client: TestClient) -> None:
    headers = auth_header(client, "resumeuser")

    resp = client.post(
        "/api/resumes",
        json={
            "full_name": "田中太郎",
            "career_summary": "キャリアサマリー",
            "self_pr": "自己PR",
            "experiences": [],
            "qualifications": [{"acquired_date": "2020-04", "name": "応用情報技術者"}],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    resume_id = resp.json()["id"]

    resp = client.get("/api/resumes/latest", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "田中太郎"
    assert resp.json()["career_summary"] == "キャリアサマリー"
    assert resp.json()["qualifications"][0]["name"] == "応用情報技術者"

    resp = client.put(
        f"/api/resumes/{resume_id}",
        json={
            "full_name": "田中花子",
            "career_summary": "更新済みサマリー",
            "self_pr": "自己PR",
            "experiences": [],
            "qualifications": [],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["career_summary"] == "更新済みサマリー"
    assert resp.json()["full_name"] == "田中花子"


def test_resume_qualifications_sorted_asc(client: TestClient) -> None:
    """資格一覧が取得日昇順で返ることを確認する。"""
    headers = auth_header(client, "resume-sort-user")

    resp = client.post(
        "/api/resumes",
        json={
            "full_name": "ソート確認",
            "career_summary": "要約",
            "self_pr": "自己PR",
            "experiences": [],
            "qualifications": [
                {"acquired_date": "2023-06", "name": "基本情報技術者"},
                {"acquired_date": "2021-03", "name": "ITパスポート"},
                {"acquired_date": "2025-01", "name": "応用情報技術者"},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.get("/api/resumes/latest", headers=headers)
    assert resp.status_code == 200
    dates = [q["acquired_date"] for q in resp.json()["qualifications"]]
    assert dates == sorted(dates), f"取得日昇順でない: {dates}"


def test_resume_qualification_date_is_year_month(client: TestClient) -> None:
    """資格取得日は在籍期間と同じ YYYY-MM で往復する（UI は type="month" に統一）。"""
    headers = auth_header(client, "resume-qual-ym-user")

    resp = client.post(
        "/api/resumes",
        json={
            "full_name": "年月確認",
            "career_summary": "要約",
            "self_pr": "自己PR",
            "experiences": [],
            "qualifications": [
                {"acquired_date": "2020-04", "name": "応用情報技術者"},
            ],
        },
        headers=headers,
    )
    assert resp.status_code == 201

    resp = client.get("/api/resumes/latest", headers=headers)
    assert resp.status_code == 200
    quals = {q["name"]: q["acquired_date"] for q in resp.json()["qualifications"]}
    assert quals["応用情報技術者"] == "2020-04"


def test_resume_round_trips_nested_structure(client: TestClient) -> None:
    headers = auth_header(client, "resume-nested-user")

    payload = {
        "full_name": "山田 太郎",
        "career_summary": "キャリアサマリー",
        "self_pr": "自己PR",
        "experiences": [
            {
                "company": "Example株式会社",
                "business_description": "SES事業",
                "start_date": "2021-04",
                "end_date": "2024-03",
                "is_current": False,
                "employee_count": "300",
                "capital": "10",
                "clients": [
                    {
                        "name": "顧客A",
                        "has_client": True,
                        "projects": [
                            {
                                "name": "API開発",
                                "start_date": "2023-01",
                                "end_date": "2024-03",
                                "is_current": False,
                                "role": "SE",
                                "description": "性能改善のため非同期化し応答時間を短縮",
                                "team": {
                                    "total": "5",
                                    "members": [{"role": "SE", "count": 3}],
                                },
                                "technology_stacks": [
                                    {"category": "language", "name": "Python"},
                                    {"category": "framework", "name": "FastAPI"},
                                ],
                                "phases": ["基本設計", "開発"],
                            }
                        ],
                    }
                ],
            }
        ],
        "qualifications": [],
    }

    resp = client.post("/api/resumes", json=payload, headers=headers)
    assert resp.status_code == 201
    resume_id = resp.json()["id"]

    resp = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    project = data["experiences"][0]["clients"][0]["projects"][0]
    assert project["name"] == "API開発"
    assert project["team"]["members"][0]["count"] == 3
    assert project["technology_stacks"][1]["name"] == "FastAPI"
    assert project["phases"] == ["基本設計", "開発"]


# ── Health Check ───────────────────────────────────────────────


def test_health_check(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


# ── 404: Not Found ─────────────────────────────────────────────


def test_resume_get_by_id(client: TestClient) -> None:
    headers = auth_header(client, "resumegetuser")
    resp = client.post(
        "/api/resumes",
        json={
            "full_name": "山田 太郎",
            "career_summary": "サマリー",
            "self_pr": "自己PR",
            "experiences": [],
            "qualifications": [],
        },
        headers=headers,
    )
    assert resp.status_code == 201
    resume_id = resp.json()["id"]

    resp = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["career_summary"] == "サマリー"


def test_resume_not_found(client: TestClient) -> None:
    headers = auth_header(client, "resume404user")
    resp = client.get(
        "/api/resumes/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert resp.status_code == 404
