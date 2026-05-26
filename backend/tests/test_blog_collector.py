"""ブログコレクター（fetch_note_articles / fetch_zenn_articles / verify_user_exists）のユニットテスト。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app.services.blog.collector import (
    BlogPlatformRequestError,
    UnsupportedBlogPlatformError,
    fetch_note_articles,
    fetch_qiita_articles,
    fetch_zenn_articles,
    normalize_username,
    verify_user_exists,
)


def _run(coro):
    """async 関数を同期的に実行するヘルパー。"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_async_client_returning_json(api_json: dict | list) -> AsyncMock:
    """raise_for_status() を通り json() で `api_json` を返す AsyncClient モックを生成する。"""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value=api_json)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_async_client_with_status(status_code: int) -> AsyncMock:
    """get() が status_code だけを持つレスポンスを返す AsyncClient モックを生成する。"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


def _mock_async_client_raising(exc: BaseException) -> AsyncMock:
    """get() が `exc` を送出する AsyncClient モックを生成する。"""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=exc)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ── fetch_note_articles テスト ───────────────────────────────────────────


def test_normalize_username_accepts_plain_username() -> None:
    assert normalize_username("zenn", "testuser") == "testuser"


def test_normalize_username_extracts_from_article_url() -> None:
    assert (
        normalize_username("zenn", "https://zenn.dev/testuser/articles/test-article")
        == "testuser"
    )


def test_normalize_username_extracts_from_note_article_url() -> None:
    assert normalize_username("note", "https://note.com/testuser/n/n123") == "testuser"


def test_normalize_username_rejects_invalid_platform_url() -> None:
    with pytest.raises(ValueError):
        normalize_username("zenn", "https://example.com/testuser")


def _note_api_response(contents: list[dict], *, is_last_page: bool = True) -> dict:
    """note API v2 のレスポンス JSON を構築するヘルパー。"""
    return {"data": {"contents": contents, "isLastPage": is_last_page}}


def test_fetch_note_articles_no_hashtags_returns_empty_tags() -> None:
    """hashtags なし → tags が空リストになること。"""
    api_json = _note_api_response(
        [
            {
                "id": 123,
                "name": "テスト記事",
                "noteUrl": "https://note.com/user/n/abc123",
                "publishAt": "2026-01-01T00:00:00.000+0900",
                "likeCount": 5,
                "body": "本文テキスト",
                "hashtags": [],
            }
        ]
    )
    mock_client = _mock_async_client_returning_json(api_json)

    with patch("app.services.blog.collector.httpx.AsyncClient", return_value=mock_client):
        articles = _run(fetch_note_articles("user"))

    assert len(articles) == 1
    assert articles[0]["tags"] == []
    assert articles[0]["likes_count"] == 5
    assert articles[0]["external_id"] == "123"


def test_fetch_note_articles_with_hashtags() -> None:
    """hashtags あり → tags に反映されること。"""
    api_json = _note_api_response(
        [
            {
                "id": 456,
                "name": "Python記事",
                "noteUrl": "https://note.com/user/n/abc456",
                "publishAt": "2026-01-01T00:00:00.000+0900",
                "likeCount": 42,
                "body": "概要",
                "hashtags": [
                    {"hashtag": {"name": "Python"}},
                    {"hashtag": {"name": "FastAPI"}},
                ],
            }
        ]
    )
    mock_client = _mock_async_client_returning_json(api_json)

    with patch("app.services.blog.collector.httpx.AsyncClient", return_value=mock_client):
        articles = _run(fetch_note_articles("user"))

    assert articles[0]["tags"] == ["Python", "FastAPI"]
    assert articles[0]["likes_count"] == 42


# ── fetch_qiita_articles テスト ──────────────────────────────────────────


def test_fetch_qiita_articles_success() -> None:
    """Qiita API から記事を正常に取得できること。"""
    api_json = [
        {
            "id": "abc12345",
            "title": "Qiitaテスト記事",
            "url": "https://qiita.com/user/items/abc12345",
            "created_at": "2026-02-01T10:00:00+09:00",
            "likes_count": 10,
            "tags": [{"name": "TypeScript"}, {"name": "React"}],
        }
    ]
    mock_client = _mock_async_client_returning_json(api_json)

    with patch("app.services.blog.collector.httpx.AsyncClient", return_value=mock_client):
        articles = _run(fetch_qiita_articles("user"))

    assert len(articles) == 1
    assert articles[0]["platform"] == "qiita"
    assert articles[0]["external_id"] == "abc12345"
    assert articles[0]["title"] == "Qiitaテスト記事"
    assert articles[0]["published_at"] == "2026-02-01"
    assert articles[0]["likes_count"] == 10
    assert articles[0]["tags"] == ["TypeScript", "React"]


# ── fetch_zenn_articles テスト ───────────────────────────────────────────


def test_fetch_zenn_articles_timeout_raises() -> None:
    """httpx.TimeoutException 発生時は例外が伝播すること。"""
    mock_client = _mock_async_client_raising(httpx.TimeoutException("timeout"))

    with patch("app.services.blog.collector.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.TimeoutException):
            _run(fetch_zenn_articles("user"))


# ── verify_user_exists テスト ────────────────────────────────────────────


def test_verify_user_exists_unsupported_platform_raises_error() -> None:
    """未対応プラットフォームでは UnsupportedBlogPlatformError が送出されること。"""
    with pytest.raises(UnsupportedBlogPlatformError):
        _run(verify_user_exists("hatena", "someuser"))


def test_verify_user_exists_zenn_user_found() -> None:
    """Zenn ユーザーが存在する場合は True を返すこと。"""
    mock_client = _mock_async_client_with_status(200)

    with patch("app.services.blog.collector.httpx.AsyncClient", return_value=mock_client):
        result = _run(verify_user_exists("zenn", "testuser"))

    assert result is True


def test_verify_user_exists_normalizes_before_request() -> None:
    """URL 入力でも正規化された username で存在確認すること。"""
    mock_client = _mock_async_client_with_status(200)

    with patch("app.services.blog.collector.httpx.AsyncClient", return_value=mock_client):
        result = _run(verify_user_exists("zenn", "https://zenn.dev/testuser/articles/test"))

    assert result is True
    mock_client.get.assert_awaited_once_with("https://zenn.dev/api/users/testuser")


def test_verify_user_exists_zenn_user_not_found() -> None:
    """Zenn ユーザーが存在しない場合は False を返すこと。"""
    mock_client = _mock_async_client_with_status(404)

    with patch("app.services.blog.collector.httpx.AsyncClient", return_value=mock_client):
        result = _run(verify_user_exists("zenn", "nonexistent"))

    assert result is False


def test_verify_user_exists_invalid_url_returns_false() -> None:
    """対応外 URL 形式は False を返すこと。"""
    assert _run(verify_user_exists("zenn", "https://example.com/testuser")) is False


def test_verify_user_exists_timeout_raises_blog_platform_request_error() -> None:
    """接続タイムアウト時は BlogPlatformRequestError が送出されること。"""
    mock_client = _mock_async_client_raising(httpx.TimeoutException("timeout"))

    with patch("app.services.blog.collector.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(BlogPlatformRequestError):
            _run(verify_user_exists("zenn", "user"))
