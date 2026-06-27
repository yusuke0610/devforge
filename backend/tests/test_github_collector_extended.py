"""
github_collector の collect_repos および _passes_filter のテスト。

対象モジュール: app.services.intelligence.github_collector
テスト方針:
  - fetch_repos_raw / fetch_languages は AsyncMock でモック化
  - 実 GitHub API は一切叩かない
  - _passes_filter は純粋関数として直接テスト
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.intelligence import github_collector
from app.services.intelligence.github.api_client import GitHubUserNotFoundError
from app.services.intelligence.github_collector import (
    RepoData,
    _collect_manifests,
    _is_excluded_manifest_path,
    _passes_filter,
    collect_repos,
)


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _today_str() -> str:
    """今日の日付を YYYY-MM-DD 形式で返す。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _recent_push() -> str:
    """フィルターを通過できる新しい pushed_at 値を返す (今日の日付)。"""
    return f"{_today_str()}T00:00:00Z"


def _make_raw_repo(
    name="repo1",
    owner="testuser",
    pushed_at=None,
    size=2,
    fork=False,
    private=False,
) -> dict:
    """テスト用の生リポジトリデータを生成するヘルパー。"""
    return {
        "name": name,
        "owner": {"login": owner},
        "description": "テストリポジトリ",
        "topics": [],
        "created_at": "2023-01-01T00:00:00Z",
        "pushed_at": pushed_at or _recent_push(),
        "fork": fork,
        "private": private,
        "size": size,
        "stargazers_count": 0,
        "default_branch": "main",
    }


# ── _passes_filter ────────────────────────────────────────────────────────


class TestPassesFilter:
    def test_passes_public_recent_repo(self):
        raw = _make_raw_repo()
        assert _passes_filter(raw, include_forks=False, cutoff_date_str="2020-01-01") is True

    def test_rejects_private_repo(self):
        raw = _make_raw_repo(private=True)
        assert _passes_filter(raw, include_forks=False, cutoff_date_str="2020-01-01") is False

    def test_rejects_fork_when_not_including_forks(self):
        raw = _make_raw_repo(fork=True)
        assert _passes_filter(raw, include_forks=False, cutoff_date_str="2020-01-01") is False

    def test_allows_fork_when_including_forks(self):
        raw = _make_raw_repo(fork=True)
        assert _passes_filter(raw, include_forks=True, cutoff_date_str="2020-01-01") is True

    def test_rejects_too_small_repo(self):
        raw = _make_raw_repo(size=0)
        assert _passes_filter(raw, include_forks=False, cutoff_date_str="2020-01-01") is False

    def test_rejects_old_pushed_at(self):
        raw = _make_raw_repo(pushed_at="2015-01-01T00:00:00Z")
        assert _passes_filter(raw, include_forks=False, cutoff_date_str="2020-01-01") is False

    def test_passes_exact_cutoff_date(self):
        raw = _make_raw_repo(pushed_at="2020-01-01T00:00:00Z")
        assert _passes_filter(raw, include_forks=False, cutoff_date_str="2020-01-01") is True

    def test_empty_pushed_at_passes(self):
        raw = _make_raw_repo()
        raw["pushed_at"] = ""
        assert _passes_filter(raw, include_forks=False, cutoff_date_str="2020-01-01") is True


# ── collect_repos ─────────────────────────────────────────────────────────


def _mock_http_client():
    """httpx.AsyncClient のコンテキストマネージャをモック化するヘルパー。"""
    mock_client = MagicMock()
    mock_client.closed = False
    # client.get は非同期メソッドのため AsyncMock が必要
    _not_found = MagicMock(status_code=404)
    mock_client.get = AsyncMock(return_value=_not_found)

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_client)

    async def _aexit(*_args, **_kwargs):
        mock_client.closed = True
        return False

    mock_http.__aexit__ = AsyncMock(side_effect=_aexit)
    return mock_http, mock_client


class TestCollectRepos:
    def _mock_collect(self, raw_repos, languages=None):
        """collect_repos の外部 API 呼び出しをすべてモック化して実行するヘルパー。"""
        mock_http, _ = _mock_http_client()
        with (
            patch("app.services.intelligence.github_collector.httpx.AsyncClient", return_value=mock_http),
            patch(
                "app.services.intelligence.github_collector.fetch_repos_raw",
                new_callable=AsyncMock,
                return_value=raw_repos,
            ),
            patch(
                "app.services.intelligence.github_collector.fetch_languages",
                new_callable=AsyncMock,
                return_value=languages if languages is not None else {"Python": 10000},
            ),
        ):
            return _run(collect_repos("testuser"))

    def test_returns_repo_data_list(self):
        """正常系: RepoData のリストが返ること。"""
        raw = [_make_raw_repo()]
        repos = self._mock_collect(raw)
        assert len(repos) == 1
        assert isinstance(repos[0], RepoData)

    def test_repo_data_fields_populated(self):
        """RepoData のフィールドが正しく設定されること。"""
        raw = [_make_raw_repo(name="my-repo", owner="testuser")]
        repos = self._mock_collect(raw, languages={"Python": 5000})
        assert repos[0].name == "my-repo"
        assert repos[0].owner == "testuser"
        assert repos[0].languages == {"Python": 5000}

    def test_empty_repos(self):
        """リポジトリが 0 件の場合、空リストが返ること。"""
        repos = self._mock_collect([])
        assert repos == []

    def test_fork_excluded_by_default(self):
        """デフォルトではフォークが除外されること。"""
        raw = [_make_raw_repo(fork=True)]
        repos = self._mock_collect(raw)
        assert repos == []

    def test_fork_included_when_requested(self):
        """include_forks=True のとき、フォークが含まれること。"""
        raw = [_make_raw_repo(fork=True)]
        mock_http, _ = _mock_http_client()
        with (
            patch("app.services.intelligence.github_collector.httpx.AsyncClient", return_value=mock_http),
            patch(
                "app.services.intelligence.github_collector.fetch_repos_raw",
                new_callable=AsyncMock,
                return_value=raw,
            ),
            patch(
                "app.services.intelligence.github_collector.fetch_languages",
                new_callable=AsyncMock,
                return_value={"Python": 1000},
            ),
        ):
            repos = _run(collect_repos("testuser", include_forks=True))
        assert len(repos) == 1
        assert repos[0].fork is True

    def test_github_user_not_found_propagates(self):
        """GitHubUserNotFoundError が伝播すること。"""
        mock_http, _ = _mock_http_client()
        with (
            patch("app.services.intelligence.github_collector.httpx.AsyncClient", return_value=mock_http),
            patch(
                "app.services.intelligence.github_collector.fetch_repos_raw",
                new_callable=AsyncMock,
                side_effect=GitHubUserNotFoundError("unknown"),
            ),
        ):
            with pytest.raises(GitHubUserNotFoundError):
                _run(collect_repos("unknown"))

    def test_on_repo_fetched_callback_called(self):
        """on_repo_fetched コールバックが各リポジトリ取得後に呼ばれること。"""
        raw = [_make_raw_repo(name=f"repo{i}") for i in range(3)]
        calls = []

        async def _on_repo_fetched(done: int, total: int) -> None:
            calls.append((done, total))

        mock_http, _ = _mock_http_client()
        with (
            patch("app.services.intelligence.github_collector.httpx.AsyncClient", return_value=mock_http),
            patch(
                "app.services.intelligence.github_collector.fetch_repos_raw",
                new_callable=AsyncMock,
                return_value=raw,
            ),
            patch(
                "app.services.intelligence.github_collector.fetch_languages",
                new_callable=AsyncMock,
                return_value={"Python": 2000},
            ),
        ):
            _run(collect_repos("testuser", on_repo_fetched=_on_repo_fetched))

        assert len(calls) == 3
        assert calls[0] == (1, 3)
        assert calls[2] == (3, 3)

    def test_repo_detail_fetch_happens_before_client_is_closed(self):
        """詳細取得は AsyncClient のコンテキスト内で行われること。"""
        raw = [_make_raw_repo()]
        mock_http, mock_client = _mock_http_client()

        async def _fetch_languages(client, *_args, **_kwargs):
            if getattr(client, "closed", False):
                raise RuntimeError("client already closed")
            return {"Python": 1234}

        with (
            patch("app.services.intelligence.github_collector.httpx.AsyncClient", return_value=mock_http),
            patch(
                "app.services.intelligence.github_collector.fetch_repos_raw",
                new_callable=AsyncMock,
                return_value=raw,
            ),
            patch(
                "app.services.intelligence.github_collector.fetch_languages",
                side_effect=_fetch_languages,
            ),
        ):
            repos = _run(collect_repos("testuser"))

        assert len(repos) == 1
        assert mock_client.closed is True

    def test_private_repo_excluded(self):
        """プライベートリポジトリは除外されること。"""
        raw = [_make_raw_repo(private=True)]
        repos = self._mock_collect(raw)
        assert repos == []

    def test_multiple_repos_returned(self):
        """複数リポジトリが正しく処理されること。"""
        raw = [_make_raw_repo(name=f"repo{i}") for i in range(5)]
        repos = self._mock_collect(raw)
        assert len(repos) == 5
        names = {r.name for r in repos}
        assert "repo0" in names
        assert "repo4" in names


# ── monorepo manifest 探索（ADR-0016 D9）───────────────────────────────────


class TestIsExcludedManifestPath:
    def test_excludes_node_modules_segment(self):
        assert _is_excluded_manifest_path("web/node_modules/x/package.json") is True

    def test_excludes_dot_venv_segment(self):
        assert _is_excluded_manifest_path(".venv/lib/requirements.txt") is True

    def test_keeps_clean_subtree_path(self):
        assert _is_excluded_manifest_path("backend/requirements.txt") is False

    def test_keeps_root_manifest(self):
        assert _is_excluded_manifest_path("package.json") is False


class TestCollectManifests:
    """`_collect_manifests` の除外 / 深さ・件数キャップ / partial / source_path。"""

    def _patched_collect(self, paths, truncated, *, monkeypatch=None):
        """fetch_manifest_paths / fetch_repo_file をモックして _collect_manifests を実行。

        fetch_repo_file は basename に応じた最小 manifest 内容を返す。fetch された
        パス一覧と (declarations, partial) を返す。
        """
        fetched: list[str] = []

        async def _fetch_repo_file(_client, _owner, _repo, path):
            fetched.append(path)
            name = path.rsplit("/", 1)[-1]
            if name == "package.json":
                return '{"dependencies": {"react": "^18.0.0"}}'
            if name in ("requirements.txt",):
                return "fastapi==0.110.0"
            return None

        with (
            patch(
                "app.services.intelligence.github_collector.fetch_manifest_paths",
                new_callable=AsyncMock,
                return_value=(paths, truncated),
            ),
            patch(
                "app.services.intelligence.github_collector.fetch_repo_file",
                side_effect=_fetch_repo_file,
            ),
        ):
            decls, partial = _run(
                _collect_manifests(MagicMock(), "u", "repo", "main")
            )
        return decls, partial, fetched

    def test_detects_subtree_manifest_and_attaches_source_path(self):
        """サブツリーの manifest を検出し source_path を付与すること（D9 a/f）。"""
        decls, partial, fetched = self._patched_collect(
            ["backend/requirements.txt"], False
        )
        assert fetched == ["backend/requirements.txt"]
        assert partial is False
        assert len(decls) == 1
        assert decls[0].name == "fastapi"
        assert decls[0].source_path == "backend/requirements.txt"

    def test_excluded_segment_paths_are_dropped(self):
        """除外セグメントを含むパスは fetch せず捨てること。partial にはしない（D9 b）。"""
        decls, partial, fetched = self._patched_collect(
            ["requirements.txt", "web/node_modules/x/package.json"], False
        )
        assert fetched == ["requirements.txt"]
        assert partial is False
        assert {d.source_path for d in decls} == {"requirements.txt"}

    def test_truncated_marks_partial(self):
        """Trees API の truncated を partial として伝播すること（D9 d）。"""
        _decls, partial, _fetched = self._patched_collect(
            ["requirements.txt"], True
        )
        assert partial is True

    def test_depth_cap_drops_deep_paths_and_marks_partial(self, monkeypatch):
        """深さ上限超の manifest は落とし partial=True にすること（D9 c/d）。"""
        monkeypatch.setattr(github_collector, "_MANIFEST_MAX_DEPTH", 2)
        decls, partial, fetched = self._patched_collect(
            ["requirements.txt", "a/b/c/requirements.txt"], False
        )
        # 深さ2まで（"requirements.txt" のみ）。"a/b/c/requirements.txt" は4セグメントで除外。
        assert fetched == ["requirements.txt"]
        assert partial is True
        assert {d.source_path for d in decls} == {"requirements.txt"}

    def test_count_cap_truncates_shallow_first_and_marks_partial(self, monkeypatch):
        """件数上限で浅い順に打ち切り partial=True にすること（D9 c/d）。"""
        monkeypatch.setattr(github_collector, "_MANIFEST_MAX_COUNT", 1)
        _decls, partial, fetched = self._patched_collect(
            ["sub/requirements.txt", "requirements.txt"], False
        )
        # 浅い順ソートで root を優先し 1 件で打ち切る。
        assert fetched == ["requirements.txt"]
        assert partial is True
