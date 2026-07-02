"""GitHub API クライアントの SSRF / パス操作対策テスト。

`api_client` は username / owner / repo を API パスへ補間する。許容パターン外の
値を渡した場合に HTTP リクエストを発行せず弾くこと（多層防御）を検証する。

非同期関数は pytest-asyncio に依存せず専用 event loop で同期的に実行する
（本リポジトリは asyncio_mode=auto を設定していないため）。
"""

import asyncio
from unittest.mock import AsyncMock

import pytest
from app.services.intelligence.github.api_client import (
    _ensure_valid_owner,
    _ensure_valid_repo,
    fetch_languages,
    fetch_repos_raw,
)
from app.services.tasks.exceptions import NonRetryableError

# パス操作・SSRF を狙う不正なユーザー名/owner 名
_MALICIOUS_OWNERS = [
    "../../etc/passwd",
    "owner/extra-segment",
    "has space",
    "user@evil.com",
    "name%2f..%2f",
    "a" * 40,  # 39 文字上限超過
    "",
]


def _run(coro):
    """async 関数を専用 event loop で同期実行する（グローバル loop を触らない）。

    mutmut 3.x は同一プロセスで pytest スイートを複数回実行するため、
    ``asyncio.set_event_loop`` / ``get_event_loop`` でグローバル loop 状態に
    触れると実行間に汚染が漏れて clean test が落ちる。ローカル loop を作って
    閉じるだけの分離パターンにして反復実行に対して冪等にする。
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.mark.parametrize("bad", _MALICIOUS_OWNERS)
def test_ensure_valid_owner_rejects_malicious(bad: str) -> None:
    """不正な owner はバリデーションで NonRetryableError を上げる。"""
    with pytest.raises(NonRetryableError):
        _ensure_valid_owner(bad)


def test_ensure_valid_repo_rejects_path_traversal() -> None:
    """repo 名のパストラバーサルを弾く。"""
    with pytest.raises(NonRetryableError):
        _ensure_valid_repo("../../secret")


def test_ensure_valid_owner_accepts_normal() -> None:
    """正当な GitHub ユーザー名は通す。"""
    _ensure_valid_owner("octocat")
    _ensure_valid_repo("my-repo.v2_final")


def test_fetch_repos_raw_rejects_bad_username_without_http() -> None:
    """不正な username では HTTP リクエストを一切発行せず弾く。"""
    client = AsyncMock()
    with pytest.raises(NonRetryableError):
        _run(fetch_repos_raw(client, "../../evil"))
    client.get.assert_not_called()


def test_fetch_languages_skips_bad_owner_without_http() -> None:
    """不正な owner/repo では HTTP を発行せず空を返す（パイプラインは継続）。"""
    client = AsyncMock()
    result = _run(fetch_languages(client, "evil/../x", "repo"))
    assert result == {}
    client.get.assert_not_called()
