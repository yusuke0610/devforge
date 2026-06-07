"""
GitHub データコレクター（オーケストレーション層）。

GitHub REST API を介してパブリックリポジトリのデータを取得します。
実際の API 呼び出しは github.api_client に委譲します。
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx

from ..tasks.exceptions import RetryableError
from .github.api_client import (
    _REPO_MAX_AGE_YEARS,
    _REPO_MIN_SIZE_BYTES,
    GITHUB_API,
    GitHubUserNotFoundError,
    fetch_languages,
    fetch_repos_raw,
)

logger = logging.getLogger(__name__)

# このモジュールの公開 API。``GitHubUserNotFoundError`` は github_link_service が
# ``from .github_collector import GitHubUserNotFoundError`` で参照するため再エクスポートする。
__all__ = [
    "RepoData",
    "collect_repos",
    "GitHubUserNotFoundError",
]


@dataclass
class RepoData:
    """リポジトリデータを保持するデータクラス。"""

    name: str
    owner: str
    description: str
    languages: Dict[str, int]  # 言語 → バイト数
    topics: List[str]
    created_at: str  # ISO 8601 形式
    pushed_at: str  # ISO 8601 形式
    fork: bool
    stargazers_count: int
    default_branch: str = field(default="main")


def _passes_filter(raw: dict, include_forks: bool, cutoff_date_str: str) -> bool:
    """リポジトリが分析対象かどうかを判定する。"""
    if raw.get("private"):
        return False
    if raw.get("fork") and not include_forks:
        return False
    if raw.get("size", 0) < (_REPO_MIN_SIZE_BYTES // 1024):
        return False
    pushed = raw.get("pushed_at", "")
    if pushed and pushed[:10] < cutoff_date_str:
        return False
    return True


async def collect_repos(
    username: str,
    token: Optional[str] = None,
    include_forks: bool = False,
    max_pages: int = 5,
    on_repo_fetched: Optional[Callable[[int, int], Awaitable[None]]] = None,
) -> List[RepoData]:
    """
    GitHub ユーザーのすべてのパブリックリポジトリを取得する。

    言語の内訳を含む RepoData のリストを返す。
    on_repo_fetched が渡された場合、各リポジトリの詳細取得後に
    on_repo_fetched(done, total) を呼び出す（進捗通知用）。
    """
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    repos: List[RepoData] = []

    try:
        async with httpx.AsyncClient(
            base_url=GITHUB_API,
            headers=headers,
            timeout=30.0,
        ) as client:
            # 1. リポジトリリストの取得
            raw_repos = await fetch_repos_raw(client, username, max_pages)
            # 2. 各リポジトリについて、言語の内訳を取得
            cutoff = datetime.now(timezone.utc).replace(
                year=datetime.now(timezone.utc).year - _REPO_MAX_AGE_YEARS,
            )
            cutoff_date_str = cutoff.strftime("%Y-%m-%d")
            filtered_raws = [r for r in raw_repos if _passes_filter(r, include_forks, cutoff_date_str)]
            total = len(filtered_raws)

            for i, raw in enumerate(filtered_raws):
                owner_login = raw["owner"]["login"]
                repo_name = raw["name"]

                languages = await fetch_languages(client, owner_login, repo_name)

                repos.append(
                    RepoData(
                        name=repo_name,
                        owner=owner_login,
                        description=raw.get("description") or "",
                        languages=languages,
                        topics=raw.get("topics") or [],
                        created_at=raw.get("created_at", ""),
                        pushed_at=raw.get("pushed_at", ""),
                        fork=raw.get("fork", False),
                        stargazers_count=raw.get("stargazers_count", 0),
                        default_branch=raw.get("default_branch", "main"),
                    )
                )

                if on_repo_fetched is not None:
                    await on_repo_fetched(i + 1, total)
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise RetryableError(f"GitHub ネットワーク障害: {exc}") from exc

    logger.info(
        "Collected %d repos for %s (skipped forks: %s)",
        len(repos),
        username,
        not include_forks,
    )
    return repos
