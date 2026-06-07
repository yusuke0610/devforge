"""
GitHub GraphQL API でコントリビューションカレンダーを取得するモジュール。

REST では取得できない「緑の四角」カレンダー（contributionsCollection）を
GraphQL から取得する。`read:user` スコープのトークンで公開プロフィールの
コントリビューション情報を読み取れる。

``contributionYears`` で貢献のある全年を取得し、年ごとに ``from``/``to`` を指定して
カレンダーを取得する（GraphQL の contributionsCollection は1リクエスト最大1年のため）。

このモジュールは連携パイプラインの**補助処理**であり、取得失敗時は
``logger.warning`` を残して空配列（または該当年のスキップ）で継続する
（主処理のリポジトリ解析を巻き添えにしない）。
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

# 貢献のある年の一覧を取得するクエリ。
_YEARS_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionYears
    }
  }
}
"""

# 指定期間（最大1年）のカレンダーを取得するクエリ。
_CALENDAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
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


async def fetch_all_contribution_calendars(
    username: str,
    token: str,
) -> list[ContributionCalendar]:
    """貢献のある全年のコントリビューションカレンダーを新しい年順で取得する。

    取得に失敗した場合（認証エラー・レート制限・ネットワーク障害・GraphQL エラー等）は
    ``logger.warning`` を残して取得できた範囲（年単位）を返す。連携自体は継続させる
    補助処理のため、例外を送出しない。

    Args:
        username: 対象 GitHub ユーザー名。
        token: 認証用アクセストークン（復号済み）。

    Returns:
        年ごとの ``ContributionCalendar`` のリスト（降順）。全失敗時は空配列。
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        years = await _fetch_contribution_years(client, username, headers)
        if not years:
            return []

        calendars: list[ContributionCalendar] = []
        # 新しい年順（降順）で取得する
        for year in sorted(years, reverse=True):
            calendar = await _fetch_calendar_for_year(client, username, year, headers)
            if calendar is not None:
                calendars.append(calendar)
        return calendars


async def _post_graphql(
    client: httpx.AsyncClient,
    headers: dict,
    variables: dict,
    query: str,
    username: str,
) -> Optional[dict]:
    """GraphQL を実行し ``data.user`` を返す。失敗時は warning を残して ``None``。"""
    try:
        resp = await client.post(
            _GRAPHQL_ENDPOINT,
            headers=headers,
            json={"query": query, "variables": variables},
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
    return user


async def _fetch_contribution_years(
    client: httpx.AsyncClient,
    username: str,
    headers: dict,
) -> list[int]:
    """貢献のある年の一覧を取得する。失敗時は空配列を返す。"""
    user = await _post_graphql(
        client, headers, {"login": username}, _YEARS_QUERY, username
    )
    if not user:
        return []
    years = (user.get("contributionsCollection") or {}).get("contributionYears")
    if not isinstance(years, list):
        logger.warning("contributionYears が取得できない (username=%s)", username)
        return []
    return [y for y in years if isinstance(y, int)]


async def _fetch_calendar_for_year(
    client: httpx.AsyncClient,
    username: str,
    year: int,
    headers: dict,
) -> Optional[ContributionCalendar]:
    """指定年のカレンダーを取得する。失敗時は warning を残して ``None``。"""
    variables = {
        "login": username,
        "from": f"{year}-01-01T00:00:00Z",
        "to": f"{year}-12-31T23:59:59Z",
    }
    user = await _post_graphql(
        client, headers, variables, _CALENDAR_QUERY, username
    )
    if not user:
        return None

    calendar_raw = (user.get("contributionsCollection") or {}).get(
        "contributionCalendar"
    )
    if not calendar_raw:
        logger.warning(
            "コントリビューションカレンダーが空 (username=%s, year=%s)", username, year
        )
        return None

    try:
        return _parse_calendar(calendar_raw, year)
    except Exception as exc:
        logger.warning(
            "コントリビューションカレンダーの解析に失敗 (username=%s, year=%s): %s",
            username,
            year,
            exc,
        )
        return None


def _parse_calendar(calendar_raw: dict, year: int) -> ContributionCalendar:
    """GraphQL の contributionCalendar を ``ContributionCalendar`` に変換する。

    不正な day エントリ（date 欠落・型不一致など）は黙って読み飛ばし、
    解析全体を巻き添えにしない（補助処理として best-effort で変換する）。
    """
    weeks: list[list[ContributionDay]] = []
    for week in calendar_raw.get("weeks", []):
        days: list[ContributionDay] = []
        for day in week.get("contributionDays", []):
            date = day.get("date")
            if not isinstance(date, str) or not date:
                # date 欠落・型不一致の day はスキップ
                continue
            count = day.get("contributionCount", 0)
            days.append(
                ContributionDay(
                    date=date,
                    count=count if isinstance(count, int) else 0,
                    level=_LEVEL_MAP.get(day.get("contributionLevel", "NONE"), 0),
                )
            )
        weeks.append(days)

    total = calendar_raw.get("totalContributions", 0)
    return ContributionCalendar(
        year=year,
        total_contributions=total if isinstance(total, int) else 0,
        weeks=weeks,
    )
