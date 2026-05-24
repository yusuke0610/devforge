"""LLM 出力のサニタイズ・null 正規化に関する単体テスト。

LLM はプロンプトの「未入力は ""」契約を破って null を返すことがあり、その値が
そのまま ResumeBase 系スキーマに渡るとバリデーションで落ちる。本テストは
`_sanitize_nulls` と `extract_structured` の両方で null 正規化が効くことを
ResumeBase 構築まで通して検証する。
"""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from app.schemas.resume import ResumeBase
from app.services.resume_import.llm_extractor import (
    _sanitize_nulls,
    extract_structured,
)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── _sanitize_nulls ─────────────────────────────────────────────────────────


def test_sanitize_nulls_drops_all_none_keys():
    """None のキーはすべて削除される（end_date 含む）。schema 側で default が効く。"""
    data = {
        "name": None,
        "challenge": None,
        "action": None,
        "result": None,
        "capital": None,
        "end_date": None,
        "company": "会社A",
    }
    cleaned = _sanitize_nulls(data)
    assert cleaned == {"company": "会社A"}


def test_sanitize_nulls_drops_end_date_none():
    """end_date の None もキーごと削除される（schema default の "" が効く）。"""
    data = {"name": "案件A", "end_date": None, "is_current": True}
    cleaned = _sanitize_nulls(data)
    assert cleaned == {"name": "案件A", "is_current": True}


def test_sanitize_nulls_recurses_into_nested_structures():
    """ネストした dict / list 内の None もすべて削除される。"""
    data = {
        "experiences": [
            {
                "company": "会社A",
                "capital": None,
                "end_date": None,
                "clients": [
                    {
                        "name": None,
                        "projects": [
                            {
                                "name": "P1",
                                "challenge": None,
                                "action": None,
                                "result": None,
                                "end_date": None,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    cleaned = _sanitize_nulls(data)
    exp = cleaned["experiences"][0]
    assert exp == {
        "company": "会社A",
        "clients": [
            {
                "projects": [
                    {"name": "P1"},
                ],
            },
        ],
    }


def test_sanitize_nulls_preserves_non_none_values():
    """非 None 値（空文字列・0・False を含む）は維持する。"""
    data = {"name": "", "count": 0, "is_current": False, "skipped": None}
    cleaned = _sanitize_nulls(data)
    assert cleaned == {"name": "", "count": 0, "is_current": False}


# ── extract_structured + ResumeBase 統合 ────────────────────────────────────


def test_extract_structured_null_output_builds_valid_resume():
    """LLM が null を返しても、サニタイズ後に ResumeBase が構築できる。

    過去ログに出ていた実エラー（experiences[0].clients[0].name=None,
    projects[0].challenge/action/result=None, experiences[3].capital=None）を
    そのまま再現したペイロード。
    """
    raw = json.dumps({
        "full_name": "山田 太郎",
        "career_summary": "バックエンドエンジニア",
        "self_pr": "API 設計が得意",
        "experiences": [
            {
                "company": "会社A",
                "business_description": "SaaS 開発",
                "start_date": "2020-04",
                "end_date": "2022-03",
                "is_current": False,
                "employee_count": "100名",
                "capital": "1億円",
                "clients": [
                    {
                        "name": None,
                        "has_client": False,
                        "projects": [
                            {
                                "name": "P1",
                                "start_date": "2020-04",
                                "end_date": "2022-03",
                                "is_current": False,
                                "role": "BE",
                                "description": "API 開発",
                                "challenge": None,
                                "action": None,
                                "result": None,
                            }
                        ],
                    }
                ],
            },
            {
                "company": "会社B",
                "business_description": "受託開発",
                "start_date": "2022-04",
                "end_date": None,
                "is_current": True,
                "employee_count": "50名",
                "capital": None,
                "clients": [],
            },
        ],
        "qualifications": [],
    })

    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=raw)

    parsed = _run(extract_structured("dummy text", mock_llm))

    # サニタイズ済みデータから ResumeBase が構築できる（= 本番ルータと同じ）
    resume = ResumeBase(**parsed)
    assert resume.full_name == "山田 太郎"
    assert len(resume.experiences) == 2

    # null だった str フィールドがすべて default の "" に丸まっている
    exp0 = resume.experiences[0]
    assert exp0.clients[0].name == ""
    proj0 = exp0.clients[0].projects[0]
    assert proj0.challenge == ""
    assert proj0.action == ""
    assert proj0.result == ""

    # 在籍中の end_date は "" に正規化される（None は schema が受け付けない）
    exp1 = resume.experiences[1]
    assert exp1.is_current is True
    assert exp1.end_date == ""
    assert exp1.capital == ""


def test_extract_structured_missing_required_top_level_keys():
    """top-level の必須キーが存在しない場合は既存補完で埋まる。

    既存挙動の回帰確認: full_name 等が `null` の場合 _sanitize_nulls が削除し、
    そのあとの top-level fallback で `""` が入る。ResumeBase は min_length=1 のため
    ValidationError になるが、これは LLM 出力としては正当な失敗ケース。
    """
    raw = json.dumps({
        "full_name": None,
        "career_summary": "概要",
        "self_pr": "PR",
    })
    mock_llm = AsyncMock()
    mock_llm.generate = AsyncMock(return_value=raw)

    parsed = _run(extract_structured("dummy text", mock_llm))

    assert parsed["full_name"] == ""
    assert parsed["experiences"] == []
    assert parsed["qualifications"] == []
    # ResumeBase 構築は min_length 違反で fail する想定（= サニタイズの責務外）
    with pytest.raises(Exception):
        ResumeBase(**parsed)
