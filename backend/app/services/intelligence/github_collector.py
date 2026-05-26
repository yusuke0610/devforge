"""
GitHub データコレクター（オーケストレーション層）。

GitHub REST API を介してパブリックリポジトリのデータを取得します。
実際の API 呼び出しは github.api_client、解析処理は github.repo_analyzer に委譲します。
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
    fetch_file_content,
    fetch_languages,
    fetch_repos_raw,
    fetch_root_files,
    fetch_subdirectory_dep_files,
)
from .github.repo_analyzer import (
    DEPENDENCY_FILES as _DEPENDENCY_FILES,
)
from .github.repo_analyzer import (
    detect_devtools_from_root_files as _detect_devtools_from_root_files,
)
from .github.repo_analyzer import (
    detect_from_dependencies as _detect_from_dependencies,
)
from .github.repo_analyzer import (
    detect_infras_from_dependencies as _detect_infras_from_dependencies,
)
from .github.repo_analyzer import (
    detect_infras_from_root_files as _detect_infras_from_root_files,
)
from .github.repo_analyzer import (
    parse_go_mod as _parse_go_mod,
)
from .github.repo_analyzer import (
    parse_package_json as _parse_package_json,
)
from .github.repo_analyzer import (
    parse_pom_xml as _parse_pom_xml,
)
from .github.repo_analyzer import (
    parse_pyproject_toml as _parse_pyproject_toml,
)
from .github.repo_analyzer import (
    parse_requirements_txt as _parse_requirements_txt,
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
    default_branch: str
    dependencies: List[str] = field(default_factory=list)
    root_files: List[str] = field(default_factory=list)
    detected_frameworks: List[str] = field(default_factory=list)  # 依存関係由来のフレームワーク
    detected_devtools: List[str] = field(default_factory=list)   # ルートファイル由来の DevTools
    detected_infras: List[str] = field(default_factory=list)     # ルートファイル由来のインフラツール


async def _parse_dependencies(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    root_files: List[str],
) -> List[str]:
    """依存関係ファイルを解析し、パッケージ名リストを返す。

    ルートファイルにない場合はサブディレクトリ（backend/ 等）もフォールバック探索する。
    """
    deps: List[str] = []

    # ルートの dep ファイルを解析
    for fname in root_files:
        if fname not in _DEPENDENCY_FILES:
            continue
        content = await fetch_file_content(client, owner, repo, fname)
        if not content:
            continue
        deps.extend(_parse_dep_content(fname, content))

    # モノレポ等でルートに dep ファイルがない場合のフォールバック
    subdir_paths = await fetch_subdirectory_dep_files(client, owner, repo, root_files)
    for path in subdir_paths:
        fname = path.split("/")[-1]
        content = await fetch_file_content(client, owner, repo, path)
        if not content:
            continue
        deps.extend(_parse_dep_content(fname, content))

    return list(set(deps))


def _parse_dep_content(filename: str, content: str) -> List[str]:
    """ファイル名に応じたパーサーでパッケージ名リストを返す。"""
    if filename == "requirements.txt":
        return _parse_requirements_txt(content)
    if filename == "pyproject.toml":
        return _parse_pyproject_toml(content)
    if filename == "package.json":
        return _parse_package_json(content)
    if filename == "pom.xml":
        return _parse_pom_xml(content)
    if filename == "go.mod":
        return _parse_go_mod(content)
    return []


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
            # 2. 各リポジトリについて、言語の内訳と構造を取得
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
                root_files = await fetch_root_files(client, owner_login, repo_name)
                dependencies = await _parse_dependencies(
                    client, owner_login, repo_name, root_files
                )
                detected_frameworks = _detect_from_dependencies(dependencies)
                detected_devtools = _detect_devtools_from_root_files(root_files)
                # インフラ: ルートファイル由来 + 依存関係由来（AWS/GCP/Azure 等）をマージ
                _infras_root = _detect_infras_from_root_files(root_files)
                _infras_deps = _detect_infras_from_dependencies(dependencies)
                _seen_infras: set = set(_infras_root)
                detected_infras = _infras_root + [
                    inf for inf in _infras_deps if inf not in _seen_infras
                ]

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
                        dependencies=dependencies,
                        root_files=root_files,
                        detected_frameworks=detected_frameworks,
                        detected_devtools=detected_devtools,
                        detected_infras=detected_infras,
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
