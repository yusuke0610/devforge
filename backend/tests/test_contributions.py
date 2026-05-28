"""
GitHub コントリビューションカレンダー取得（GraphQL）のテスト。

対象モジュール: app.services.intelligence.github.contributions
テスト方針:
  - httpx.AsyncClient をモック化し、実 GitHub API は叩かない
  - 補助処理として失敗時に None を返す（例外を送出しない）ことを検証
  - contributionLevel → 0–4 の正規化を検証
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from app.services.intelligence.github.contributions import (
    _parse_calendar,
    fetch_contribution_calendar,
)


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_client(*, status_code=200, payload=None, post_side_effect=None):
    """POST レスポンスを返すモック AsyncClient を生成する。"""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    if post_side_effect is not None:
        mock_client.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json = MagicMock(return_value=payload or {})
        mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


_CALENDAR_PAYLOAD = {
    "data": {
        "user": {
            "contributionsCollection": {
                "contributionCalendar": {
                    "totalContributions": 42,
                    "weeks": [
                        {
                            "contributionDays": [
                                {
                                    "date": "2024-01-01",
                                    "contributionCount": 0,
                                    "contributionLevel": "NONE",
                                },
                                {
                                    "date": "2024-01-02",
                                    "contributionCount": 5,
                                    "contributionLevel": "SECOND_QUARTILE",
                                },
                            ]
                        },
                        {
                            "contributionDays": [
                                {
                                    "date": "2024-01-08",
                                    "contributionCount": 12,
                                    "contributionLevel": "FOURTH_QUARTILE",
                                },
                            ]
                        },
                    ],
                }
            }
        }
    }
}


def _patch_client(mock_client):
    return patch(
        "app.services.intelligence.github.contributions.httpx.AsyncClient",
        return_value=mock_client,
    )


class TestFetchContributionCalendar:
    def test_success_parses_calendar(self):
        """正常系: totalContributions と週ごとの level が正しく取得されること。"""
        with _patch_client(_make_mock_client(payload=_CALENDAR_PAYLOAD)):
            calendar = _run(fetch_contribution_calendar("gh-user", "token123"))

        assert calendar is not None
        assert calendar.total_contributions == 42
        assert len(calendar.weeks) == 2
        # NONE → 0, SECOND_QUARTILE → 2, FOURTH_QUARTILE → 4
        assert [d.level for d in calendar.weeks[0]] == [0, 2]
        assert calendar.weeks[0][1].count == 5
        assert calendar.weeks[1][0].level == 4
        assert calendar.weeks[1][0].date == "2024-01-08"

    def test_graphql_errors_returns_none(self):
        """GraphQL errors を含む応答では None を返すこと。"""
        payload = {"data": {"user": None}, "errors": [{"message": "Bad creds"}]}
        with _patch_client(_make_mock_client(payload=payload)):
            calendar = _run(fetch_contribution_calendar("gh-user", "token123"))
        assert calendar is None

    def test_user_none_returns_none(self):
        """user が null の応答では None を返すこと。"""
        payload = {"data": {"user": None}}
        with _patch_client(_make_mock_client(payload=payload)):
            calendar = _run(fetch_contribution_calendar("gh-user", "token123"))
        assert calendar is None

    def test_non_200_returns_none(self):
        """HTTP 401 等では None を返すこと（例外を投げない）。"""
        with _patch_client(_make_mock_client(status_code=401, payload={})):
            calendar = _run(fetch_contribution_calendar("gh-user", "token123"))
        assert calendar is None

    def test_network_error_returns_none(self):
        """ネットワーク障害でも例外を投げず None を返すこと（補助処理）。"""
        with _patch_client(
            _make_mock_client(post_side_effect=httpx.ConnectError("boom"))
        ):
            calendar = _run(fetch_contribution_calendar("gh-user", "token123"))
        assert calendar is None


class TestParseCalendar:
    def test_level_mapping_and_defaults(self):
        """contributionLevel が 0–4 に正規化され、未知値は 0 になること。"""
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
        calendar = _parse_calendar(raw)
        assert calendar.total_contributions == 3
        assert [d.level for d in calendar.weeks[0]] == [1, 3, 0]

    def test_empty_weeks(self):
        """weeks が空でも壊れないこと。"""
        calendar = _parse_calendar({"totalContributions": 0, "weeks": []})
        assert calendar.total_contributions == 0
        assert calendar.weeks == []
