"""Zenn / note からブログ記事を取得するサービス。"""

import asyncio
from urllib.parse import urlparse

import httpx

from ...core.logging_utils import get_logger

logger = get_logger(__name__)

# 記事取得用のデフォルトタイムアウト（全ページフェッチに耐えられる長さ）
_FETCH_TIMEOUT_SECONDS = 30.0

# ユーザー存在確認用のタイムアウト（軽量リクエスト想定）
_VERIFY_TIMEOUT_SECONDS = 10.0


class UnsupportedBlogPlatformError(ValueError):
    """未対応プラットフォームが指定された場合の例外。"""


class BlogAccountNotFoundError(ValueError):
    """対象アカウントが見つからない場合の例外。"""


class BlogPlatformRequestError(RuntimeError):
    """外部プラットフォームへの接続失敗を表す例外。"""


_BLOG_PLATFORM_HOSTS = {
    "zenn": {"zenn.dev", "www.zenn.dev"},
    "note": {"note.com", "www.note.com"},
    "qiita": {"qiita.com", "www.qiita.com"},
}

# verify_user_exists 用のユーザー存在確認エンドポイント。
# (URL テンプレート, クエリパラメータ) を platform ごとに引く。
_VERIFY_ENDPOINTS: dict[str, tuple[str, dict | None]] = {
    "zenn": ("https://zenn.dev/api/users/{username}", None),
    "note": (
        "https://note.com/api/v2/creators/{username}/contents",
        {"kind": "note", "page": 1},
    ),
    "qiita": ("https://qiita.com/api/v2/users/{username}", None),
}


def _truncate_date(value: str | None) -> str | None:
    """ISO 日付文字列の先頭 10 文字（``YYYY-MM-DD``）を返す。空なら ``None``。"""
    return value[:10] if value else None


def _build_article(
    platform: str,
    *,
    external_id: str,
    title: str,
    url: str,
    published_at: str | None,
    likes_count: int,
    tags: list[str],
    summary: str = "",
) -> dict:
    """各プラットフォーム共通の記事 dict を組み立てる。

    この dict の形が記事取り込みの暗黙の契約であり、
    ``repositories.blog.BlogArticleRepository._apply_article_payload`` が同じキーを期待する。
    キーを増減する場合は両者を併せて更新すること。
    """
    return {
        "platform": platform,
        "external_id": external_id,
        "title": title,
        "url": url,
        "published_at": published_at,
        "likes_count": likes_count,
        "summary": summary,
        "tags": tags,
    }


def _parse_platform_url(raw_username: str, allowed_hosts: set[str]):
    if raw_username.startswith(("http://", "https://")):
        parsed = urlparse(raw_username)
    elif any(raw_username == host or raw_username.startswith(f"{host}/") for host in allowed_hosts):
        parsed = urlparse(f"https://{raw_username}")
    else:
        return None

    if parsed.netloc.lower() not in allowed_hosts:
        raise ValueError(raw_username)
    return parsed


def _path_segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment]


def normalize_username(platform: str, username: str) -> str:
    """ユーザー入力からプラットフォーム固有の username を抽出する。"""
    value = username.strip().rstrip("/")
    if not value:
        raise ValueError(username)

    if platform not in _BLOG_PLATFORM_HOSTS:
        raise UnsupportedBlogPlatformError(platform)

    parsed = _parse_platform_url(value, _BLOG_PLATFORM_HOSTS[platform])
    if parsed is None:
        if "/" in value:
            raise ValueError(username)
        return value

    segments = _path_segments(parsed.path)
    if not segments:
        raise ValueError(username)

    first_segment = segments[0]
    if platform == "zenn" and first_segment in {"api", "p"}:
        raise ValueError(username)
    if platform in {"note", "qiita"} and first_segment == "api":
        raise ValueError(username)
    return first_segment


def _zenn_article_belongs_to_username(item: dict, username: str) -> bool:
    path = item.get("path")
    if isinstance(path, str) and path.startswith(f"/{username}/articles/"):
        return True

    user = item.get("user")
    if isinstance(user, dict) and user.get("username") == username:
        return True
    return False


async def fetch_zenn_articles(username: str) -> list[dict]:
    """Zenn API から記事を取得する。全ページ分をフェッチ。"""
    articles: list[dict] = []
    page = 1

    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECONDS) as client:
        while True:
            resp = await client.get(
                "https://zenn.dev/api/articles",
                params={"username": username, "order": "latest", "page": page},
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("articles", [])

            if items and any(not _zenn_article_belongs_to_username(item, username) for item in items):
                logger.warning(
                    "Zenn API returned articles for an unexpected user: requested=%s",
                    username,
                )
                raise BlogAccountNotFoundError(username)

            for item in items:
                slug = item.get("slug", "")
                topics = item.get("topics", [])
                tag_names = [
                    t.get("display_name") or t.get("name", "")
                    for t in topics
                    if isinstance(t, dict)
                ]
                articles.append(
                    _build_article(
                        "zenn",
                        external_id=slug,
                        title=item.get("title", ""),
                        url=f"https://zenn.dev/{username}/articles/{slug}",
                        published_at=_truncate_date(item.get("published_at")),
                        likes_count=item.get("liked_count", 0),
                        tags=tag_names,
                    )
                )

            next_page = data.get("next_page")
            if not next_page:
                break
            page = next_page

    return articles


async def fetch_note_articles(username: str) -> list[dict]:
    """note API v2 から記事を取得する。全ページ分をフェッチ。"""
    articles: list[dict] = []
    page = 1
    headers = {"User-Agent": "DevForge/1.0"}

    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECONDS, headers=headers) as client:
        while True:
            resp = await client.get(
                f"https://note.com/api/v2/creators/{username}/contents",
                params={"kind": "note", "page": page},
            )
            resp.raise_for_status()
            data = resp.json()

            notes = data.get("data", {}).get("contents", [])
            if not notes:
                break

            for item in notes:
                hashtags = item.get("hashtags", [])
                tag_names = [
                    h.get("hashtag", {}).get("name", "")
                    for h in hashtags
                    if isinstance(h, dict)
                ]
                body = item.get("body") or ""

                articles.append(
                    _build_article(
                        "note",
                        external_id=str(item.get("id", "")),
                        title=item.get("name", ""),
                        url=item.get("noteUrl", ""),
                        published_at=_truncate_date(item.get("publishAt")),
                        likes_count=item.get("likeCount", 0),
                        summary=body[:500],
                        tags=[t for t in tag_names if t],
                    )
                )

            is_last_page = data.get("data", {}).get("isLastPage", True)
            if is_last_page:
                break
            page += 1
            await asyncio.sleep(0.5)

    return articles


async def fetch_qiita_articles(username: str) -> list[dict]:
    """Qiita API v2 から記事を取得する。全ページ分をフェッチ。"""
    articles: list[dict] = []
    page = 1
    per_page = 100

    async with httpx.AsyncClient(timeout=_FETCH_TIMEOUT_SECONDS) as client:
        while True:
            resp = await client.get(
                f"https://qiita.com/api/v2/users/{username}/items",
                params={"page": page, "per_page": per_page},
            )
            resp.raise_for_status()
            data = resp.json()

            if not data:
                break

            for item in data:
                tag_names = [t.get("name", "") for t in item.get("tags", [])]
                articles.append(
                    _build_article(
                        "qiita",
                        external_id=item.get("id", ""),
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        published_at=_truncate_date(item.get("created_at")),
                        likes_count=item.get("likes_count", 0),
                        tags=tag_names,
                    )
                )

            if len(data) < per_page:
                break
            page += 1
            await asyncio.sleep(0.5)

    return articles


async def verify_user_exists(platform: str, username: str) -> bool:
    """プラットフォーム上にユーザーが存在するか検証する。"""
    try:
        normalized_username = normalize_username(platform, username)
    except UnsupportedBlogPlatformError:
        raise
    except ValueError:
        return False

    endpoint = _VERIFY_ENDPOINTS.get(platform)
    if endpoint is None:
        raise UnsupportedBlogPlatformError(platform)
    url_template, params = endpoint

    try:
        async with httpx.AsyncClient(timeout=_VERIFY_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                url_template.format(username=normalized_username), params=params
            )
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        logger.warning("プラットフォーム %s への接続に失敗しました", platform)
        raise BlogPlatformRequestError(platform) from None


async def fetch_articles(platform: str, username: str) -> list[dict]:
    """プラットフォームに応じて適切なフェッチャーを呼ぶ。"""
    if platform == "zenn":
        return await fetch_zenn_articles(username)
    if platform == "note":
        return await fetch_note_articles(username)
    if platform == "qiita":
        return await fetch_qiita_articles(username)
    raise UnsupportedBlogPlatformError(platform)
