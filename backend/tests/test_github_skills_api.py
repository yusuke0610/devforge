"""GitHub 連携スキル（3 層）の永続化と取得エンドポイントのテスト（ADR-0016）。"""

from app.models import GitHubSkillEvidence
from app.repositories import UserRepository
from app.repositories.skill import GitHubSkillRepository
from app.services.intelligence.skills import DetectedSkill, EvidenceRecord

from conftest import auth_header


def _user_id(client, username: str) -> str:
    user = UserRepository(client._db_session).get_by_username(username)
    assert user is not None
    return user.id


def _sample_detected() -> list[DetectedSkill]:
    return [
        DetectedSkill(
            kind="language",
            canonical_name="Python",
            ecosystem="",
            parent=None,
            display_name=None,
            evidence=[
                EvidenceRecord(
                    repo_full_name="u/a",
                    repo_url="https://github.com/u/a",
                    signal_source="language_bytes",
                    confidence=0.8,
                    language_bytes=8000,
                )
            ],
        ),
        DetectedSkill(
            kind="package",
            canonical_name="react",
            ecosystem="npm",
            parent=None,
            display_name=None,
            evidence=[
                EvidenceRecord(
                    repo_full_name="u/a",
                    repo_url="https://github.com/u/a",
                    signal_source="manifest_declared",
                    confidence=0.6,
                    dependency_kind="direct",
                    manifest_path="web/package.json",
                    partial_scan=True,
                )
            ],
        ),
    ]


def _sample_infra_detected() -> list[DetectedSkill]:
    """kind=infra の provider / resource スキル（D10）。"""
    return [
        DetectedSkill(
            kind="infra",
            canonical_name="aws",
            ecosystem="terraform",
            parent=None,
            display_name=None,
            evidence=[
                EvidenceRecord(
                    repo_full_name="u/a",
                    repo_url="https://github.com/u/a",
                    signal_source="infra_declared",
                    confidence=0.5,
                    manifest_path="infra/main.tf",
                )
            ],
        ),
        DetectedSkill(
            kind="infra",
            canonical_name="aws_s3_bucket",
            ecosystem="terraform",
            parent=None,
            display_name=None,
            evidence=[
                EvidenceRecord(
                    repo_full_name="u/a",
                    repo_url="https://github.com/u/a",
                    signal_source="infra_declared",
                    confidence=0.6,
                    manifest_path="infra/main.tf",
                )
            ],
        ),
    ]


def test_skills_requires_auth(client) -> None:
    """未認証では 401 になること。"""
    resp = client.get("/api/github-link/skills")
    assert resp.status_code == 401


def test_skills_empty_when_not_linked(client) -> None:
    """連携前は空配列を返すこと。"""
    headers = auth_header(client, "skilluser_empty")
    resp = client.get("/api/github-link/skills", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"skills": []}


def test_replace_then_get_returns_layers(client) -> None:
    """永続化したスキルが evidence 付きで取得でき、言語の ecosystem は null になること。"""
    headers = auth_header(client, "skilluser_full")
    uid = _user_id(client, "skilluser_full")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_sample_detected())

    resp = client.get("/api/github-link/skills", headers=headers)
    assert resp.status_code == 200
    by_name = {s["canonical_name"]: s for s in resp.json()["skills"]}

    python = by_name["Python"]
    assert python["kind"] == "language"
    assert python["ecosystem"] is None  # 言語は "" → null へ正規化
    assert python["evidence"][0]["language_bytes"] == 8000
    assert python["evidence"][0]["signal_source"] == "language_bytes"
    assert python["proficiency"] is None  # Layer 3 は本フェーズ未投入

    react = by_name["react"]
    assert react["ecosystem"] == "npm"
    assert react["evidence"][0]["dependency_kind"] == "direct"
    # D9: manifest パスと partial フラグが往復で永続化・取得されること。
    assert react["evidence"][0]["manifest_path"] == "web/package.json"
    assert react["evidence"][0]["partial_scan"] is True
    # 言語根拠には manifest_path / partial が立たないこと。
    assert python["evidence"][0]["manifest_path"] is None
    assert python["evidence"][0]["partial_scan"] is False


def test_infra_skills_persist_and_return(client) -> None:
    """kind=infra の provider / resource が往復で永続化・取得できること（D10）。"""
    headers = auth_header(client, "skilluser_infra")
    uid = _user_id(client, "skilluser_infra")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(
        _sample_infra_detected()
    )

    resp = client.get("/api/github-link/skills", headers=headers)
    assert resp.status_code == 200
    by_name = {s["canonical_name"]: s for s in resp.json()["skills"]}

    provider = by_name["aws"]
    assert provider["kind"] == "infra"
    assert provider["ecosystem"] == "terraform"
    assert provider["evidence"][0]["signal_source"] == "infra_declared"
    assert provider["evidence"][0]["manifest_path"] == "infra/main.tf"

    resource = by_name["aws_s3_bucket"]
    assert resource["kind"] == "infra"
    assert resource["evidence"][0]["confidence"] == 0.6


def test_replace_is_idempotent(client) -> None:
    """洗い替えで前回分が消えること（再連携で古いスキルが残らない）。"""
    headers = auth_header(client, "skilluser_idem")
    uid = _user_id(client, "skilluser_idem")
    repo = GitHubSkillRepository(client._db_session, uid)
    repo.replace_for_user(_sample_detected())
    repo.replace_for_user([_sample_detected()[0]])  # 2 回目は Python のみ

    resp = client.get("/api/github-link/skills", headers=headers)
    names = {s["canonical_name"] for s in resp.json()["skills"]}
    assert names == {"Python"}

    # 削除された react の evidence が孤児として残っていないこと（FK 非依存の ORM 削除）。
    # SQLite テストエンジンは PRAGMA foreign_keys=ON でないため、DB の CASCADE では消えない。
    remaining_evidence = client._db_session.query(GitHubSkillEvidence).count()
    assert remaining_evidence == 1  # Python の 1 件のみ


def test_skills_are_scoped_per_user(client) -> None:
    """他ユーザーのスキルが混ざらないこと。"""
    auth_header(client, "skilluser_a")
    uid_a = _user_id(client, "skilluser_a")
    GitHubSkillRepository(client._db_session, uid_a).replace_for_user(_sample_detected())

    # auth_header は client の Cookie を差し替えるため、最後に認証したユーザーで動く。
    # user_b で認証 → 空、user_a へ再認証 → 2 件、で分離を検証する。
    headers_b = auth_header(client, "skilluser_b")
    resp_b = client.get("/api/github-link/skills", headers=headers_b)
    assert resp_b.json() == {"skills": []}

    headers_a = auth_header(client, "skilluser_a")
    resp_a = client.get("/api/github-link/skills", headers=headers_a)
    assert len(resp_a.json()["skills"]) == 2
