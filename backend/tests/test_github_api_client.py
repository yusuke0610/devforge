"""github/api_client の fetch_repo_tree のテスト（ADR-0016 D9・D6）。

recursive Trees API のレスポンスをモックし、実 GitHub API は叩かない。
basename / 拡張子の絞り込みは collector 側の責務なので、ここでは「全 blob パス +
truncated 返却」のみを検証する（manifest と source の両方がこの単一ツリーを共有する）。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from app.services.intelligence.github.api_client import (
    fetch_languages,
    fetch_repo_file,
    fetch_repo_tree,
)
from app.services.tasks.exceptions import RetryableError


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _client_with_tree(tree, truncated=False, status_code=200):
    """Trees API レスポンスを返す AsyncClient モックを生成する。"""
    resp = MagicMock(status_code=status_code)
    resp.headers = {}
    resp.json = MagicMock(return_value={"tree": tree, "truncated": truncated})
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    return client


def _client_with_status(status_code, headers=None):
    """任意ステータス・ヘッダのレスポンスを返す AsyncClient モックを生成する。"""
    resp = MagicMock(status_code=status_code)
    resp.headers = headers or {}
    resp.json = MagicMock(return_value={})
    resp.text = ""
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    return client


def test_returns_all_blob_paths():
    """blob の相対パスをすべて返し、ディレクトリ（tree）は除外すること。"""
    tree = [
        {"type": "blob", "path": "package.json"},
        {"type": "blob", "path": "backend/requirements.txt"},
        {"type": "blob", "path": "src/app.py"},
        {"type": "tree", "path": "backend"},  # ディレクトリは除外
    ]
    client = _client_with_tree(tree)
    paths, truncated = _run(fetch_repo_tree(client, "u", "repo", "main"))
    assert set(paths) == {
        "package.json",
        "backend/requirements.txt",
        "src/app.py",
    }
    assert truncated is False


def test_propagates_truncated_flag():
    """Trees API の truncated を第 2 戻り値で返すこと。"""
    client = _client_with_tree([{"type": "blob", "path": "go.mod"}], truncated=True)
    paths, truncated = _run(fetch_repo_tree(client, "u", "repo", "main"))
    assert paths == ["go.mod"]
    assert truncated is True


def test_non_200_returns_partial():
    """非 200 は「走査不能」として ([], True) を返すこと（依存ゼロと区別 / D9(d)）。"""
    client = _client_with_tree([], status_code=404)
    assert _run(fetch_repo_tree(client, "u", "repo", "main")) == ([], True)


def test_http_error_returns_partial():
    """httpx.HTTPError も走査不能として ([], True) を返すこと。"""
    client = MagicMock()
    client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
    assert _run(fetch_repo_tree(client, "u", "repo", "main")) == ([], True)


def test_invalid_owner_repo_returns_empty():
    """不正な owner/repo は走査対象ですらないため API を叩かず ([], False) を返すこと。"""
    client = _client_with_tree([{"type": "blob", "path": "go.mod"}])
    result = _run(fetch_repo_tree(client, "../evil", "repo", "main"))
    assert result == ([], False)
    client.get.assert_not_called()


def test_rate_limited_403_raises_retryable():
    """レート制限の 403（X-RateLimit-Remaining:0）は partial 握り込みではなく
    RetryableError を raise し、連携全体をリトライ経路へ乗せること（#485）。"""
    client = _client_with_status(
        403, headers={"x-ratelimit-remaining": "0", "retry-after": "42"}
    )
    with pytest.raises(RetryableError) as exc:
        _run(fetch_repo_tree(client, "u", "repo", "main"))
    assert exc.value.retry_after == 42


def test_429_raises_retryable():
    """429 Too Many Requests も RetryableError（retry_after 付き）で raise すること（#485）。"""
    client = _client_with_status(429, headers={"retry-after": "30"})
    with pytest.raises(RetryableError) as exc:
        _run(fetch_repo_tree(client, "u", "repo", "main"))
    assert exc.value.retry_after == 30


def test_genuine_403_returns_partial():
    """レート制限でない 403（残量あり = 権限エラー等）はリトライさせず
    従来どおり partial 扱い（[], True）で返すこと（#485）。"""
    client = _client_with_status(403, headers={"x-ratelimit-remaining": "57"})
    assert _run(fetch_repo_tree(client, "u", "repo", "main")) == ([], True)


def test_languages_rate_limited_raises_retryable():
    """fetch_languages もレート制限 403 を {} で握り込まず RetryableError を raise すること
    （同一ホットパスの兄弟 fetch も #485 で統一）。"""
    client = _client_with_status(403, headers={"x-ratelimit-remaining": "0"})
    with pytest.raises(RetryableError):
        _run(fetch_languages(client, "u", "repo"))


def test_languages_genuine_403_returns_empty():
    """レート制限でない 403 は言語情報を欠いたまま {} で best-effort 継続すること。"""
    client = _client_with_status(403, headers={"x-ratelimit-remaining": "57"})
    assert _run(fetch_languages(client, "u", "repo")) == {}


def test_repo_file_rate_limited_403_raises_retryable():
    """fetch_repo_file もレート制限 403 を None で握り込まず RetryableError を raise すること
    （同一ホットパスの兄弟 fetch も #485 で統一）。"""
    client = _client_with_status(
        403, headers={"x-ratelimit-remaining": "0", "retry-after": "42"}
    )
    with pytest.raises(RetryableError) as exc:
        _run(fetch_repo_file(client, "u", "repo", "requirements.txt"))
    assert exc.value.retry_after == 42


def test_repo_file_429_raises_retryable():
    """fetch_repo_file の 429 も RetryableError（retry_after 付き）で raise すること（#485）。"""
    client = _client_with_status(429, headers={"retry-after": "30"})
    with pytest.raises(RetryableError) as exc:
        _run(fetch_repo_file(client, "u", "repo", "requirements.txt"))
    assert exc.value.retry_after == 30


def test_repo_file_genuine_403_returns_none():
    """レート制限でない 403（残量あり = 権限エラー等）はリトライさせず
    従来どおり None（当該 manifest をスキップ）で best-effort 継続すること（#485）。"""
    client = _client_with_status(403, headers={"x-ratelimit-remaining": "57"})
    assert _run(fetch_repo_file(client, "u", "repo", "requirements.txt")) is None
