"""高コスト業務経路の rate limit (429) 回帰テスト。

外部 API / タスク起動を伴う経路に `@limiter.limit` が付いていることを、
上限超過で 429 が返ることで保証する（security.md §rate limit）。
"""

from app.main import limiter
from app.repositories import UserRepository
from fastapi.testclient import TestClient

from conftest import auth_header


def test_github_link_run_rate_limited(client: TestClient) -> None:
    """POST /api/github-link/run が 5/分の上限超で 429 を返す。"""
    headers = auth_header(client, "rl-gh-user")
    # /run は連携済み GitHub アカウント（github_login）を要求するため事前にセットする
    db = client._db_session
    user = UserRepository(db).get_by_username("rl-gh-user")
    user.github_login = "octocat"
    db.commit()

    limiter.reset()
    statuses: list[int] = []
    for _ in range(8):
        resp = client.post(
            "/api/github-link/run",
            json={"include_forks": False},
            headers=headers,
        )
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            break
    assert 429 in statuses, f"429 が観測されなかった: {statuses}"
    limiter.reset()


def test_blog_sync_rate_limited(client: TestClient) -> None:
    """POST /api/blog/accounts/{id}/sync が 10/分の上限超で 429 を返す。

    存在しない account_id でも rate limit はハンドラ本体より前に評価されるため、
    上限超過で 429 になることを検証できる。
    """
    headers = auth_header(client, "rl-blog-user")
    limiter.reset()
    statuses: list[int] = []
    for _ in range(13):
        resp = client.post("/api/blog/accounts/nonexistent/sync", headers=headers)
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            break
    assert 429 in statuses, f"429 が観測されなかった: {statuses}"
    limiter.reset()
