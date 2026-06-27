"""
GitHub データコレクター（オーケストレーション層）。

GitHub REST API を介してパブリックリポジトリのデータを取得します。
実際の API 呼び出しは github.api_client に委譲します。
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
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
    fetch_manifest_paths,
    fetch_repo_file,
    fetch_repos_raw,
)
from .skills.manifests import MANIFEST_FILENAMES, parse_manifest
from .skills.types import PackageDeclaration

logger = logging.getLogger(__name__)

# monorepo manifest 探索のヒューリスティック（ADR-0016 D9）。閾値は運用で調整しうるが、
# env_keys 同期コストに見合わないためモジュール定数として持つ（チューニングはコード変更）。
# D9(b): パスのいずれかのセグメントがこの集合に該当したら manifest 候補から除外する。
_MANIFEST_PATH_EXCLUDE_SEGMENTS = frozenset(
    {
        "node_modules",
        "vendor",
        ".venv",
        "venv",
        "site-packages",
        "bower_components",
        "third_party",
        "testdata",
        "dist",
        "build",
        ".git",
    }
)
# D9(c): manifest パスのセグメント数上限（例: a/b/c/package.json = 4）。
_MANIFEST_MAX_DEPTH = 4
# D9(c): 1 リポあたり fetch する manifest 件数上限。
_MANIFEST_MAX_COUNT = 20

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
    # declare ステージ: manifest が宣言する依存（D7・D9。サブツリー含む）。未取得なら空。
    package_declarations: List[PackageDeclaration] = field(default_factory=list)
    # D9(d): manifest 走査が網羅的でない（truncated / cap で打ち切り）場合 True。
    manifest_scan_partial: bool = False


def _is_excluded_manifest_path(path: str) -> bool:
    """パスのいずれかのセグメントが除外集合に該当するか（D9(b)）。"""
    return any(seg in _MANIFEST_PATH_EXCLUDE_SEGMENTS for seg in path.split("/"))


async def _collect_manifests(
    client: httpx.AsyncClient, owner: str, repo: str, default_branch: str
) -> tuple[List[PackageDeclaration], bool]:
    """サブツリーを含む manifest を取得・解析して依存宣言を返す（declare / D7・D9）。

    recursive Trees API で候補パスを列挙し、除外セグメント（D9(b)）・深さ/件数キャップ
    （D9(c)）でフィルタしてから本文を取得する。取得・解析失敗はベストエフォートで握りつぶす
    （1 リポの失敗で連携全体を落とさない）。第 2 戻り値は走査が部分的だったか（D9(d)）。
    """
    paths, truncated = await fetch_manifest_paths(
        client, owner, repo, default_branch, MANIFEST_FILENAMES
    )
    # D9(b): 除外セグメントを含むパスを捨てる（取得済みツリーの in-memory フィルタ）。
    candidates = [p for p in paths if not _is_excluded_manifest_path(p)]
    # D9(c): 浅い順に並べ、深さ上限超を落とし、件数上限で打ち切る。
    candidates.sort(key=lambda p: (p.count("/"), p))
    within_depth = [p for p in candidates if p.count("/") + 1 <= _MANIFEST_MAX_DEPTH]
    depth_dropped = len(within_depth) < len(candidates)
    selected = within_depth[:_MANIFEST_MAX_COUNT]
    count_dropped = len(within_depth) > _MANIFEST_MAX_COUNT
    partial = bool(truncated or depth_dropped or count_dropped)
    if partial:
        logger.warning(
            "manifest 探索が部分的: %s/%s (truncated=%s, depth_dropped=%s, count_dropped=%s)",
            owner,
            repo,
            truncated,
            depth_dropped,
            count_dropped,
        )

    declarations: List[PackageDeclaration] = []
    for path in selected:
        content = await fetch_repo_file(client, owner, repo, path)
        if not content:
            continue
        filename = path.rsplit("/", 1)[-1]
        # D9(f): 検出した相対パスを証跡として各宣言に付与する。
        declarations.extend(
            replace(decl, source_path=path) for decl in parse_manifest(filename, content)
        )
    return declarations, partial


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
    collect_manifests: bool = False,
) -> List[RepoData]:
    """
    GitHub ユーザーのすべてのパブリックリポジトリを取得する。

    言語の内訳を含む RepoData のリストを返す。
    on_repo_fetched が渡された場合、各リポジトリの詳細取得後に
    on_repo_fetched(done, total) を呼び出す（進捗通知用）。
    collect_manifests=True のとき、直下 manifest を解析して package_declarations を埋める（declare / D7）。
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

                default_branch = raw.get("default_branch", "main")
                declarations: List[PackageDeclaration] = []
                manifest_partial = False
                if collect_manifests:
                    declarations, manifest_partial = await _collect_manifests(
                        client, owner_login, repo_name, default_branch
                    )

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
                        default_branch=default_branch,
                        package_declarations=declarations,
                        manifest_scan_partial=manifest_partial,
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
