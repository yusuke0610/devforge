"""
GitHub GraphQL API でコントリビューションカレンダーを取得するモジュール。

REST では取得できない「緑の四角」カレンダー（contributionsCollection）を
GraphQL から取得する。`read:user` スコープのトークンで公開プロフィールの
コントリビューション情報を読み取れる。

このモジュールは連携パイプラインの**補助処理**であり、取得失敗時は
``logger.warning`` を残して ``None`` を返す（主処理のリポジトリ解析を巻き添えにしない）。
"""

import logging
from typing import Optional

import httpx

from ....schemas.github_link import ContributionCalendar, ContributionDay
from .api_client import GITHUB_API

logger = logging.getLogger(__name__)

_GRAPHQL_ENDPOINT = f"{GITHUB_API}/graphql"

# GraphQL の contributionLevel enum を 0–4 の整数に正規化する対応表。
_LEVEL_MAP = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

_CONTRIBUTION_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""


async def fetch_contribution_calendar(
    username: str,
    token: str,
) -> Optional[ContributionCalendar]:
    """GitHub のコントリビューションカレンダー（直近1年）を取得する。

    取得に失敗した場合（認証エラー・レート制限・ネットワーク障害・GraphQL エラー等）は
    ``logger.warning`` を残して ``None`` を返す。連携自体は継続させる補助処理のため、
    例外を送出しない。

    Args:
        username: 対象 GitHub ユーザー名。
        token: 認証用アクセストークン（復号済み）。

    Returns:
        ``ContributionCalendar`` または取得失敗時は ``None``。
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _GRAPHQL_ENDPOINT,
                headers=headers,
                json={
                    "query": _CONTRIBUTION_QUERY,
                    "variables": {"login": username},
                },
            )
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
        logger.warning(
            "コントリビューション取得でネットワーク障害 (username=%s): %s",
            username,
            exc,
        )
        return None

    if resp.status_code != 200:
        logger.warning(
            "コントリビューション取得が HTTP %s で失敗 (username=%s)",
            resp.status_code,
            username,
        )
        return None

    try:
        payload = resp.json()
    except ValueError:
        logger.warning("コントリビューション応答の JSON 解析に失敗 (username=%s)", username)
        return None

    if payload.get("errors"):
        logger.warning(
            "コントリビューション取得で GraphQL エラー (username=%s): %s",
            username,
            payload["errors"],
        )
        return None

    user = (payload.get("data") or {}).get("user")
    if not user:
        logger.warning("コントリビューション対象ユーザーが見つからない (username=%s)", username)
        return None

    calendar_raw = (user.get("contributionsCollection") or {}).get(
        "contributionCalendar"
    )
    if not calendar_raw:
        logger.warning("コントリビューションカレンダーが空 (username=%s)", username)
        return None

    return _parse_calendar(calendar_raw)


def _parse_calendar(calendar_raw: dict) -> ContributionCalendar:
    """GraphQL の contributionCalendar を ``ContributionCalendar`` に変換する。"""
    weeks: list[list[ContributionDay]] = []
    for week in calendar_raw.get("weeks", []):
        days = [
            ContributionDay(
                date=day["date"],
                count=day.get("contributionCount", 0),
                level=_LEVEL_MAP.get(day.get("contributionLevel", "NONE"), 0),
            )
            for day in week.get("contributionDays", [])
        ]
        weeks.append(days)

    return ContributionCalendar(
        total_contributions=calendar_raw.get("totalContributions", 0),
        weeks=weeks,
    )
