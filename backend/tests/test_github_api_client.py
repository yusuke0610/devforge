"""github/api_client の fetch_repo_tree のテスト（ADR-0016 D9・D6）。

recursive Trees API のレスポンスをモックし、実 GitHub API は叩かない。
basename / 拡張子の絞り込みは collector 側の責務なので、ここでは「全 blob パス +
truncated 返却」のみを検証する（manifest と source の両方がこの単一ツリーを共有する）。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
from app.services.intelligence.github.api_client import fetch_repo_tree


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _client_with_tree(tree, truncated=False, status_code=200):
    """Trees API レスポンスを返す AsyncClient モックを生成する。"""
    resp = MagicMock(status_code=status_code)
    resp.json = MagicMock(return_value={"tree": tree, "truncated": truncated})
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
