"""
GitHub REST API 呼び出しを担うモジュール。

リポジトリ一覧・言語情報などの純粋な API 通信を行う。
"""

import logging
import re
import time
from typing import Any, Dict, List

import httpx

from ....services.tasks.exceptions import NonRetryableError, RetryableError

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"

# GitHub の owner（ユーザー/Organization）名と repo 名の許容パターン。
# owner: 英数字とハイフンのみ。repo: 英数字 . _ - のみ。
# API パスへ補間する前にこのパターンで検証し、不正文字によるパス操作・SSRF を防ぐ（多層防御）。
# repo は連続ドット（".."）とドットのみの名前（"." / ".." 等）を否定先読みで拒否し、
# パストラバーサル相当の入力を URL 補間前に弾く。
_OWNER_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,39}$")
_REPO_PATTERN = re.compile(r"^(?!.*\.\.)(?!\.+$)[A-Za-z0-9._-]{1,100}$")


def _ensure_valid_owner(owner: str) -> None:
    """owner（GitHub ユーザー/Org 名）が許容パターンに合致するか検証する。"""
    if not _OWNER_PATTERN.fullmatch(owner or ""):
        raise NonRetryableError(f"不正な GitHub ユーザー名: {owner!r}")


def _ensure_valid_repo(repo: str) -> None:
    """repo 名が許容パターンに合致するか検証する。"""
    if not _REPO_PATTERN.fullmatch(repo or ""):
        raise NonRetryableError(f"不正な GitHub リポジトリ名: {repo!r}")


def _is_valid_owner_repo(owner: str, repo: str) -> bool:
    """owner / repo が両方とも許容パターンに合致するか（多層防御の軽量判定）。"""
    return bool(_OWNER_PATTERN.fullmatch(owner or "")) and bool(
        _REPO_PATTERN.fullmatch(repo or "")
    )


# 一時障害とみなす HTTP ステータスコード
_RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

# この年数以内にプッシュされたリポジトリのみを取得
_REPO_MAX_AGE_YEARS = 3

# これより小さいリポジトリはスキップ（バイト）
_REPO_MIN_SIZE_BYTES = 1024


class GitHubUserNotFoundError(Exception):
    """GitHub ユーザーが見つからない場合の例外。"""

    def __init__(self, username: str):
        self.username = username
        super().__init__(f"GitHub user not found: {username}")


async def fetch_repos_raw(
    client: httpx.AsyncClient,
    username: str,
    max_pages: int = 5,
) -> List[Dict[str, Any]]:
    """
    指定ユーザーの全パブリックリポジトリを取得する（ページネーションあり）。

    - ユーザーが存在しない場合は ``GitHubUserNotFoundError`` を発生させる
    - レート制限（403 + rate limit ヘッダ / 429）は ``RetryableError`` を raise する
    - 5xx も ``RetryableError`` を raise する
    - その他の 4xx は ``NonRetryableError`` を raise する
    """
    _ensure_valid_owner(username)
    raw_repos: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        resp = await client.get(
            f"/users/{username}/repos",
            params={
                "per_page": 100,
                "page": page,
                "sort": "pushed",
                "type": "owner",
            },
        )
        if resp.status_code == 404:
            raise GitHubUserNotFoundError(username)
        if resp.status_code == 403:
            # GitHub は rate limit でも 403 を返すため、ヘッダで判別する
            if _is_rate_limited(resp):
                retry_after = _retry_after_from_github(resp)
                logger.warning(
                    "GitHub API rate limit hit (retry_after=%s)", retry_after,
                )
                raise RetryableError(
                    "GitHub API rate limit", retry_after=retry_after,
                )
            raise NonRetryableError(f"GitHub API 403 Forbidden: {resp.text[:200]}")
        if resp.status_code == 429:
            retry_after = _retry_after_from_github(resp)
            raise RetryableError(
                "GitHub API 429 Too Many Requests", retry_after=retry_after,
            )
        if resp.status_code in _RETRYABLE_STATUS_CODES:
            raise RetryableError(f"GitHub API {resp.status_code}")
        if 400 <= resp.status_code < 500:
            raise NonRetryableError(
                f"GitHub API {resp.status_code}: {resp.text[:200]}"
            )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        raw_repos.extend(batch)
    return raw_repos


def _is_rate_limited(response: httpx.Response) -> bool:
    """GitHub のレスポンスがレート制限起因かを判定する。"""
    remaining = response.headers.get("x-ratelimit-remaining")
    return remaining == "0"


def _retry_after_from_github(response: httpx.Response) -> float | None:
    """``Retry-After`` ヘッダまたは ``X-RateLimit-Reset`` から待機秒数を算出する。"""
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return float(retry_after)
        except (TypeError, ValueError):
            pass
    reset = response.headers.get("x-ratelimit-reset")
    if reset:
        try:
            # Unix timestamp。現在時刻との差分を返す（負値にならないよう 0 下限）。
            return max(0.0, float(reset) - time.time())
        except (TypeError, ValueError):
            pass
    return None


async def fetch_languages(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
) -> Dict[str, int]:
    """リポジトリの言語バイト数を取得する。"""
    if not _is_valid_owner_repo(owner, repo):
        logger.warning("不正な owner/repo をスキップ: %s/%s", owner, repo)
        return {}
    try:
        resp = await client.get(f"/repos/{owner}/{repo}/languages")
        if resp.status_code == 403:
            logger.warning("Rate limit on languages for %s/%s", owner, repo)
            return {}
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError:
        logger.warning("Failed to fetch languages for %s/%s", owner, repo)
        return {}


async def fetch_manifest_paths(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    default_branch: str,
    manifest_filenames: frozenset[str],
) -> tuple[List[str], bool]:
    """recursive Trees API でサブツリーを含む manifest パス一覧を取得する（declare / D7・D9）。

    ``GET /git/trees/{default_branch}?recursive=1`` を 1 回呼び、blob のうち basename が
    ``manifest_filenames`` に一致する相対パスだけを返す（1 リポ 1 コール / D9(a)）。
    第 2 戻り値は GitHub が木構造を打ち切ったか（``truncated`` / D9(d)）。

    除外リストや深さ・件数キャップといった探索ポリシーは呼び出し側（collector）の責務とし、
    ここでは「API 呼び出し + basename フィルタ + truncated 返却」に留める。manifest 取得は
    ベストエフォート（1 リポの失敗で連携全体を落とさない）なので、失敗時は ``([], False)``。
    """
    if not _is_valid_owner_repo(owner, repo):
        return [], False
    branch = default_branch or "main"
    try:
        resp = await client.get(
            f"/repos/{owner}/{repo}/git/trees/{branch}",
            params={"recursive": "1"},
        )
        if resp.status_code != 200:
            return [], False
        data = resp.json()
        if not isinstance(data, dict):
            return [], False
        tree = data.get("tree")
        if not isinstance(tree, list):
            return [], False
        paths = [
            entry["path"]
            for entry in tree
            if entry.get("type") == "blob"
            and entry.get("path")
            and entry["path"].rsplit("/", 1)[-1] in manifest_filenames
        ]
        return paths, bool(data.get("truncated"))
    except httpx.HTTPError:
        logger.warning("Failed to fetch git tree for %s/%s", owner, repo)
        return [], False


async def fetch_repo_file(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
) -> str | None:
    """リポジトリ内のテキストファイル内容を取得する（manifest 本文 / D7）。

    取得できなければ ``None``。生コードは呼び出し側で parse 後に破棄する想定（D6）。
    """
    if not _is_valid_owner_repo(owner, repo):
        return None
    try:
        resp = await client.get(
            f"/repos/{owner}/{repo}/contents/{path}",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if resp.status_code != 200:
            return None
        return resp.text
    except httpx.HTTPError:
        logger.warning("Failed to fetch %s for %s/%s", path, owner, repo)
        return None
