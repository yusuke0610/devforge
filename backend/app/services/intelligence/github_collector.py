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
    fetch_repo_file,
    fetch_repo_tree,
    fetch_repos_raw,
)
from .skills.imports import scanner_for_extension
from .skills.manifests import MANIFEST_FILENAMES, parse_manifest
from .skills.types import PackageDeclaration

logger = logging.getLogger(__name__)

# monorepo 探索のヒューリスティック（ADR-0016 D9）。閾値は運用で調整しうるが、
# env_keys 同期コストに見合わないためモジュール定数として持つ（チューニングはコード変更）。
# D9(b): パスのいずれかのセグメントがこの集合に該当したら候補から除外する（manifest / source 共通）。
_PATH_EXCLUDE_SEGMENTS = frozenset(
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
# D6: verify で 1 リポあたり fetch するソースファイル件数上限（import サンプリングの打ち切り）。
_SOURCE_MAX_COUNT = 30
# D6: verify 対象ソースのセグメント数上限（浅い側を優先サンプリング）。
_SOURCE_MAX_DEPTH = 6

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
    # verify ステージ（D6）: import 解析で実際に使われていた名前の集合（ecosystem → import 名）。
    # aggregator が direct 宣言と照合し actual_import 証跡へ昇格させる素にする。未取得なら空。
    imported_symbols: Dict[str, set] = field(default_factory=dict)
    # D9(d): ツリー走査（manifest / source）が網羅的でない（truncated / cap で打ち切り）場合 True。
    manifest_scan_partial: bool = False


def _is_excluded_path(path: str) -> bool:
    """パスのいずれかのセグメントが除外集合に該当するか（D9(b)。manifest / source 共通）。"""
    return any(seg in _PATH_EXCLUDE_SEGMENTS for seg in path.split("/"))


def _select_shallow(paths: List[str], max_depth: int, max_count: int) -> tuple[List[str], bool]:
    """除外・浅い順ソート・深さ/件数キャップで候補を絞る（D9(b)(c) / D6 サンプリング）。

    戻り値は (採用パス, 打ち切りが発生したか)。
    """
    candidates = [p for p in paths if not _is_excluded_path(p)]
    candidates.sort(key=lambda p: (p.count("/"), p))
    within_depth = [p for p in candidates if p.count("/") + 1 <= max_depth]
    depth_dropped = len(within_depth) < len(candidates)
    selected = within_depth[:max_count]
    count_dropped = len(within_depth) > max_count
    return selected, bool(depth_dropped or count_dropped)


async def _collect_repo_signals(
    client: httpx.AsyncClient, owner: str, repo: str, default_branch: str
) -> tuple[List[PackageDeclaration], Dict[str, set], bool]:
    """1 回のツリー取得から declare（manifest）と verify（import 解析）の両シグナルを集める。

    recursive Trees API を **1 回だけ**呼び（D9(a)）、その結果を manifest 探索と source 探索で
    共有する。manifest は宣言依存（D7・D9）、source は実 import（D6）を抽出する。いずれも
    除外セグメント（D9(b)）・深さ/件数キャップ（D9(c) / D6 サンプリング）で絞る。取得・解析
    失敗はベストエフォートで握りつぶす（1 リポの失敗で連携全体を落とさない）。

    戻り値は (依存宣言, ecosystem→import名集合, 走査が部分的だったか / D9(d))。
    """
    tree_paths, truncated = await fetch_repo_tree(client, owner, repo, default_branch)

    # ── declare: manifest を basename で抽出して解析する ──────────────────────
    manifest_paths = [
        p for p in tree_paths if p.rsplit("/", 1)[-1] in MANIFEST_FILENAMES
    ]
    selected_manifests, manifest_dropped = _select_shallow(
        manifest_paths, _MANIFEST_MAX_DEPTH, _MANIFEST_MAX_COUNT
    )
    declarations: List[PackageDeclaration] = []
    for path in selected_manifests:
        content = await fetch_repo_file(client, owner, repo, path)
        if not content:
            continue
        filename = path.rsplit("/", 1)[-1]
        # D9(f): 検出した相対パスを証跡として各宣言に付与する。
        declarations.extend(
            replace(decl, source_path=path) for decl in parse_manifest(filename, content)
        )

    # ── verify: direct 宣言のあるエコシステムだけソースを import 解析する（D6）──
    direct_ecosystems = {
        decl.ecosystem for decl in declarations if decl.dependency_kind == "direct"
    }
    imported_symbols: Dict[str, set] = {}
    source_dropped = False
    if direct_ecosystems:
        source_candidates = []
        for path in tree_paths:
            scanner = scanner_for_extension(path)
            if scanner is not None and scanner.ecosystem in direct_ecosystems:
                source_candidates.append(path)
        selected_sources, source_dropped = _select_shallow(
            source_candidates, _SOURCE_MAX_DEPTH, _SOURCE_MAX_COUNT
        )
        for path in selected_sources:
            scanner = scanner_for_extension(path)
            if scanner is None:
                continue
            content = await fetch_repo_file(client, owner, repo, path)
            if not content:
                continue
            # 生コードは scan 後に破棄（永続化しない / D6）。
            imported_symbols.setdefault(scanner.ecosystem, set()).update(
                scanner.scan(content)
            )

    partial = bool(truncated or manifest_dropped or source_dropped)
    if partial:
        logger.warning(
            "ツリー走査が部分的: %s/%s (truncated=%s, manifest_dropped=%s, source_dropped=%s)",
            owner,
            repo,
            truncated,
            manifest_dropped,
            source_dropped,
        )
    return declarations, imported_symbols, partial


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
    collect_manifests=True のとき、1 回のツリー取得から manifest 宣言（declare / D7・D9）と
    import 実使用（verify / D6）の両シグナルを集め、package_declarations と imported_symbols を埋める。
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
                imported_symbols: Dict[str, set] = {}
                scan_partial = False
                if collect_manifests:
                    declarations, imported_symbols, scan_partial = (
                        await _collect_repo_signals(
                            client, owner_login, repo_name, default_branch
                        )
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
                        imported_symbols=imported_symbols,
                        manifest_scan_partial=scan_partial,
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
