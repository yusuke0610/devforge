"""
GitHub コントリビューションカレンダー取得（GraphQL）のテスト。

対象モジュール: app.services.intelligence.github.contributions
テスト方針:
  - httpx.AsyncClient をモック化し、実 GitHub API は叩かない
  - 補助処理として失敗時に空配列を返す（例外を送出しない）ことを検証
  - contributionLevel → 0–4 の正規化を検証
  - contributionYears から年ごとに取得し、新しい年順で返すことを検証
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from app.services.intelligence.github.contributions import (
    _parse_calendar,
    fetch_all_contribution_calendars,
)


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_client(*, post_responses=None, post_side_effect=None):
    """POST レスポンスを順番に返すモック AsyncClient を生成する。

    post_responses は (status_code, payload) のタプル列。post を呼ぶたびに
    先頭から順に返す（年一覧 → 各年カレンダーの順で消費される）。
    """
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    if post_side_effect is not None:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        responses = []
        for status_code, payload in post_responses or []:
            mock_resp = MagicMock()
            mock_resp.status_code = status_code
            mock_resp.json = MagicMock(return_value=payload or {})
            responses.append(mock_resp)
        mock_client.post = AsyncMock(side_effect=responses)
    return mock_client


def _years_payload(years):
    return {
        "data": {"user": {"contributionsCollection": {"contributionYears": years}}}
    }


def _calendar_payload(total, weeks):
    return {
        "data": {
            "user": {
                "contributionsCollection": {
                    "contributionCalendar": {
                        "totalContributions": total,
                        "weeks": weeks,
                    }
                }
            }
        }
    }


_WEEKS_2024 = [
    {
        "contributionDays": [
            {"date": "2024-01-01", "contributionCount": 0, "contributionLevel": "NONE"},
            {
                "date": "2024-01-02",
                "contributionCount": 5,
                "contributionLevel": "SECOND_QUARTILE",
            },
        ]
    },
]


def _patch_client(mock_client):
    return patch(
        "app.services.intelligence.github.contributions.httpx.AsyncClient",
        return_value=mock_client,
    )


class TestFetchAllContributionCalendars:
    def test_returns_calendars_in_descending_year_order(self):
        """貢献のある全年を新しい年順（降順）で返し、各 year が付与されること。"""
        client = _make_mock_client(
            post_responses=[
                (200, _years_payload([2023, 2024])),  # 年一覧
                (200, _calendar_payload(42, _WEEKS_2024)),  # 2024（降順で先に取得）
                (200, _calendar_payload(10, [])),  # 2023
            ]
        )
        with _patch_client(client):
            ok, calendars = _run(fetch_all_contribution_calendars("gh-user", "token123"))

        assert ok is True
        assert [c.year for c in calendars] == [2024, 2023]
        assert calendars[0].total_contributions == 42
        # NONE → 0, SECOND_QUARTILE → 2
        assert [d.level for d in calendars[0].weeks[0]] == [0, 2]
        assert calendars[1].total_contributions == 10

    def test_no_years_returns_success_empty(self):
        """contributionYears が空（貢献ゼロ）なら success=True で空配列を返すこと。

        取得自体は成功しているため、呼び出し側で警告を立てさせない。
        """
        client = _make_mock_client(post_responses=[(200, _years_payload([]))])
        with _patch_client(client):
            ok, calendars = _run(fetch_all_contribution_calendars("gh-user", "token123"))
        assert ok is True
        assert calendars == []

    def test_years_query_graphql_error_returns_failure(self):
        """年一覧取得が GraphQL エラーなら success=False・空配列を返すこと（例外を投げない）。"""
        payload = {"data": {"user": None}, "errors": [{"message": "Bad creds"}]}
        client = _make_mock_client(post_responses=[(200, payload)])
        with _patch_client(client):
            ok, calendars = _run(fetch_all_contribution_calendars("gh-user", "token123"))
        assert ok is False
        assert calendars == []

    def test_failed_year_is_skipped(self):
        """一部の年の取得に失敗しても、成功した年だけを返すこと（success=True）。"""
        client = _make_mock_client(
            post_responses=[
                (200, _years_payload([2023, 2024])),
                (200, _calendar_payload(42, _WEEKS_2024)),  # 2024 成功
                (500, {}),  # 2023 は失敗 → スキップ
            ]
        )
        with _patch_client(client):
            ok, calendars = _run(fetch_all_contribution_calendars("gh-user", "token123"))
        assert ok is True
        assert [c.year for c in calendars] == [2024]

    def test_network_error_returns_failure(self):
        """ネットワーク障害でも例外を投げず success=False・空配列を返すこと（補助処理）。"""
        client = _make_mock_client(post_side_effect=httpx.ConnectError("boom"))
        with _patch_client(client):
            ok, calendars = _run(fetch_all_contribution_calendars("gh-user", "token123"))
        assert ok is False
        assert calendars == []


class TestParseCalendar:
    def test_level_mapping_and_defaults(self):
        """contributionLevel が 0–4 に正規化され、未知値は 0 になること。year も付与される。"""
        raw = {
            "totalContributions": 3,
            "weeks": [
                {
                    "contributionDays": [
                        {"date": "2024-02-01", "contributionCount": 1, "contributionLevel": "FIRST_QUARTILE"},
                        {"date": "2024-02-02", "contributionCount": 2, "contributionLevel": "THIRD_QUARTILE"},
                        {"date": "2024-02-03", "contributionCount": 0, "contributionLevel": "UNKNOWN"},
                    ]
                }
            ],
        }
        calendar = _parse_calendar(raw, 2024)
        assert calendar.year == 2024
        assert calendar.total_contributions == 3
        assert [d.level for d in calendar.weeks[0]] == [1, 3, 0]

    def test_empty_weeks(self):
        """weeks が空でも壊れないこと。"""
        calendar = _parse_calendar({"totalContributions": 0, "weeks": []}, 2022)
        assert calendar.year == 2022
        assert calendar.total_contributions == 0
        assert calendar.weeks == []
