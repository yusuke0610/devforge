"""github/api_client の fetch_manifest_paths のテスト（ADR-0016 D9）。

recursive Trees API のレスポンスをモックし、実 GitHub API は叩かない。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
from app.services.intelligence.github.api_client import fetch_manifest_paths
from app.services.intelligence.skills.manifests import MANIFEST_FILENAMES


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


def test_returns_blob_paths_matching_manifest_basenames():
    """basename が既知 manifest 名の blob だけを返すこと。"""
    tree = [
        {"type": "blob", "path": "package.json"},
        {"type": "blob", "path": "backend/requirements.txt"},
        {"type": "blob", "path": "README.md"},  # manifest でない
        {"type": "tree", "path": "backend"},  # ディレクトリ
    ]
    client = _client_with_tree(tree)
    paths, truncated = _run(
        fetch_manifest_paths(client, "u", "repo", "main", MANIFEST_FILENAMES)
    )
    assert set(paths) == {"package.json", "backend/requirements.txt"}
    assert truncated is False


def test_propagates_truncated_flag():
    """Trees API の truncated を第 2 戻り値で返すこと。"""
    client = _client_with_tree(
        [{"type": "blob", "path": "go.mod"}], truncated=True
    )
    paths, truncated = _run(
        fetch_manifest_paths(client, "u", "repo", "main", MANIFEST_FILENAMES)
    )
    assert paths == ["go.mod"]
    assert truncated is True


def test_non_200_returns_partial():
    """非 200 は「走査不能」として ([], True) を返すこと（依存ゼロと区別 / D9(d)）。"""
    client = _client_with_tree([], status_code=404)
    assert _run(
        fetch_manifest_paths(client, "u", "repo", "main", MANIFEST_FILENAMES)
    ) == ([], True)


def test_http_error_returns_partial():
    """httpx.HTTPError も走査不能として ([], True) を返すこと。"""
    client = MagicMock()
    client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
    assert _run(
        fetch_manifest_paths(client, "u", "repo", "main", MANIFEST_FILENAMES)
    ) == ([], True)


def test_invalid_owner_repo_returns_empty():
    """不正な owner/repo は走査対象ですらないため API を叩かず ([], False) を返すこと。"""
    client = _client_with_tree([{"type": "blob", "path": "go.mod"}])
    result = _run(
        fetch_manifest_paths(client, "../evil", "repo", "main", MANIFEST_FILENAMES)
    )
    assert result == ([], False)
    client.get.assert_not_called()
