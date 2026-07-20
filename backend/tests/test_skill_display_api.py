"""スキル表示名の human-in-the-loop 提案・確定 API のテスト（ADR-0016 D11）。

DB はモックせず実 SQLite セッションに当てる。LLM のみモックする。propose の 402/502、
confirm の authz、確定の反映、連携の洗い替えに対する確定の耐性を検証する。
"""

import json

from app.repositories import UserRepository
from app.repositories.skill import (
    DisplayDecisionInput,
    GitHubSkillDisplayDecisionRepository,
    GitHubSkillRepository,
)
from app.services.agent.llm.base import LLMClient, LLMError, LLMResult
from app.services.agent.skill_display import proposer
from app.services.intelligence.skills import DetectedSkill, EvidenceRecord

from conftest import auth_header


def _user_id(client, username: str) -> str:
    user = UserRepository(client._db_session).get_by_username(username)
    assert user is not None
    return user.id


def _detected() -> list[DetectedSkill]:
    return [
        DetectedSkill(
            kind="package",
            canonical_name="@aws-sdk/client-s3",
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
                )
            ],
        ),
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
    ]


class _FakeLLM(LLMClient):
    """固定応答を返す LLM クライアント（または例外を送出）。"""

    def __init__(self, response):
        self._response = response

    async def generate(self, system_prompt, messages, output_schema, model_id) -> LLMResult:
        if isinstance(self._response, Exception):
            raise self._response
        return LLMResult(text=self._response, input_tokens=5, output_tokens=7)


def _mock_llm(monkeypatch, response) -> None:
    monkeypatch.setattr(proposer, "get_llm_client", lambda provider: _FakeLLM(response))


# ---- propose -------------------------------------------------------------


def test_propose_requires_auth(client) -> None:
    """未認証は 401。"""
    resp = client.post("/api/github-link/skills/display-names/propose", json={})
    assert resp.status_code == 401


def test_propose_404_when_no_skills(client) -> None:
    """スキルが無ければ 404（先に連携が必要）。"""
    headers = auth_header(client, "disp_none")
    resp = client.post(
        "/api/github-link/skills/display-names/propose", json={"model": "haiku"}, headers=headers
    )
    assert resp.status_code == 404


def test_propose_happy_returns_groups(client, monkeypatch) -> None:
    """package/infra に対し agent 提案（グループ + メンバー identity）が返ること。

    language（Python）は提案対象外に絞られるため、LLM が誤って language token を返しても
    許可集合に無く破棄される（A: language 除外 / ADR-0016 D11）。
    """
    headers = auth_header(client, "disp_happy")
    uid = _user_id(client, "disp_happy")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())
    _mock_llm(
        monkeypatch,
        json.dumps(
            {
                "groups": [
                    {"display_name": "Amazon S3", "members": ["npm:@aws-sdk/client-s3"]},
                    # language は候補から外れており token も許可外。破棄されることを検証する
                    {"display_name": "Python", "members": ["language:Python"]},
                ]
            }
        ),
    )

    resp = client.post(
        "/api/github-link/skills/display-names/propose", json={"model": "haiku"}, headers=headers
    )
    assert resp.status_code == 200
    groups = {g["display_name"]: g for g in resp.json()["groups"]}
    # language グループは許可外 token のみで空になり破棄される
    assert set(groups) == {"Amazon S3"}
    s3_member = groups["Amazon S3"]["members"][0]
    assert s3_member["kind"] == "package"
    assert s3_member["ecosystem"] == "npm"
    assert s3_member["canonical_name"] == "@aws-sdk/client-s3"


def test_propose_404_when_only_languages(client) -> None:
    """language しか無い場合は提案対象なしで 404（A: language 除外 / D11）。"""
    headers = auth_header(client, "disp_langonly")
    uid = _user_id(client, "disp_langonly")
    # _detected() の language 1 件だけを投入する
    GitHubSkillRepository(client._db_session, uid).replace_for_user([_detected()[1]])
    resp = client.post(
        "/api/github-link/skills/display-names/propose", json={"model": "haiku"}, headers=headers
    )
    assert resp.status_code == 404


def test_propose_402_for_paid_model_without_credits(client) -> None:
    """有料モデルは残高 0 だと LLM を呼ぶ前に 402。"""
    headers = auth_header(client, "disp_paid")
    uid = _user_id(client, "disp_paid")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())
    resp = client.post(
        "/api/github-link/skills/display-names/propose", json={"model": "sonnet"}, headers=headers
    )
    assert resp.status_code == 402


def test_propose_502_on_llm_error(client, monkeypatch) -> None:
    """LLM 失敗は 502（AGENT_LLM_ERROR）。"""
    headers = auth_header(client, "disp_llmerr")
    uid = _user_id(client, "disp_llmerr")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())
    _mock_llm(monkeypatch, LLMError("down"))

    resp = client.post(
        "/api/github-link/skills/display-names/propose", json={"model": "haiku"}, headers=headers
    )
    assert resp.status_code == 502


# ---- confirm -------------------------------------------------------------


def test_confirm_rejects_unknown_identity(client) -> None:
    """当該ユーザーの検出済みスキルに無い identity の確定は 422。"""
    headers = auth_header(client, "disp_badid")
    uid = _user_id(client, "disp_badid")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())

    resp = client.put(
        "/api/github-link/skills/display-decisions",
        json={
            "decisions": [
                {
                    "kind": "package",
                    "ecosystem": "npm",
                    "canonical_name": "does-not-exist",
                    "display_name": "偽物",
                }
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_confirm_persists_and_get_reflects(client) -> None:
    """確定した表示名・グループが GET /skills に反映されること。"""
    headers = auth_header(client, "disp_confirm")
    uid = _user_id(client, "disp_confirm")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())

    resp = client.put(
        "/api/github-link/skills/display-decisions",
        json={
            "decisions": [
                {
                    "kind": "package",
                    "ecosystem": "npm",
                    "canonical_name": "@aws-sdk/client-s3",
                    "display_name": "Amazon S3",
                    "group_id": "grp-aws",
                    "source": "human",
                }
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200
    by_name = {s["canonical_name"]: s for s in resp.json()["skills"]}
    s3 = by_name["@aws-sdk/client-s3"]
    assert s3["confirmed_display_name"] == "Amazon S3"
    assert s3["group_id"] == "grp-aws"
    assert s3["decision_source"] == "human"
    assert s3["decision_reviewed"] is True
    # 未確定スキルは確定フィールドが null
    assert by_name["Python"]["confirmed_display_name"] is None

    # GET でも同じ確定が返ること
    get_resp = client.get("/api/github-link/skills", headers=headers)
    got = {s["canonical_name"]: s for s in get_resp.json()["skills"]}
    assert got["@aws-sdk/client-s3"]["confirmed_display_name"] == "Amazon S3"


def test_confirm_upsert_overwrites_existing(client) -> None:
    """同一 identity の再確定は上書き（重複行を作らない）。"""
    auth_header(client, "disp_upsert")
    uid = _user_id(client, "disp_upsert")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())
    repo = GitHubSkillDisplayDecisionRepository(client._db_session, uid)
    repo.upsert_many(
        [DisplayDecisionInput("package", "npm", "@aws-sdk/client-s3", "旧S3")]
    )
    repo.upsert_many(
        [DisplayDecisionInput("package", "npm", "@aws-sdk/client-s3", "Amazon S3")]
    )

    decisions = repo.get_for_user()
    assert len(decisions) == 1
    assert decisions[0].display_name == "Amazon S3"


def test_decision_survives_relink_wipe(client) -> None:
    """連携再実行（Layer 1-2 洗い替え）後も確定表示名が残ること（D11 の核心）。"""
    headers = auth_header(client, "disp_relink")
    uid = _user_id(client, "disp_relink")
    skill_repo = GitHubSkillRepository(client._db_session, uid)
    skill_repo.replace_for_user(_detected())
    GitHubSkillDisplayDecisionRepository(client._db_session, uid).upsert_many(
        [DisplayDecisionInput("package", "npm", "@aws-sdk/client-s3", "Amazon S3", "grp-aws")]
    )

    # 再連携相当の洗い替え（同じ identity のスキルを作り直す）
    skill_repo.replace_for_user(_detected())

    resp = client.get("/api/github-link/skills", headers=headers)
    by_name = {s["canonical_name"]: s for s in resp.json()["skills"]}
    # スキルは作り直されたが、確定表示名は独立テーブルに残っているので復活する
    assert by_name["@aws-sdk/client-s3"]["confirmed_display_name"] == "Amazon S3"
    assert by_name["@aws-sdk/client-s3"]["group_id"] == "grp-aws"


# ---- reset（解除） -------------------------------------------------------


def test_reset_requires_auth(client) -> None:
    """未認証は 401。"""
    resp = client.request(
        "DELETE",
        "/api/github-link/skills/display-decisions",
        json={"identities": []},
    )
    assert resp.status_code == 401


def test_reset_rejects_unknown_identity(client) -> None:
    """当該ユーザーの検出済みスキルに無い identity のリセットは 422。"""
    headers = auth_header(client, "disp_reset_badid")
    uid = _user_id(client, "disp_reset_badid")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())

    resp = client.request(
        "DELETE",
        "/api/github-link/skills/display-decisions",
        json={
            "identities": [
                {"kind": "package", "ecosystem": "npm", "canonical_name": "does-not-exist"}
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 422


def test_reset_removes_decision_and_reverts_to_default(client) -> None:
    """確定行を削除し、確定表示名・グループが機械デフォルト（null）へ戻ること（#496）。"""
    headers = auth_header(client, "disp_reset")
    uid = _user_id(client, "disp_reset")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())
    GitHubSkillDisplayDecisionRepository(client._db_session, uid).upsert_many(
        [DisplayDecisionInput("package", "npm", "@aws-sdk/client-s3", "Amazon S3", "grp-aws")]
    )

    resp = client.request(
        "DELETE",
        "/api/github-link/skills/display-decisions",
        json={
            "identities": [
                {"kind": "package", "ecosystem": "npm", "canonical_name": "@aws-sdk/client-s3"}
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200
    by_name = {s["canonical_name"]: s for s in resp.json()["skills"]}
    s3 = by_name["@aws-sdk/client-s3"]
    # 確定行が消え、確定フィールドは null（機械デフォルトへ完全リセット）
    assert s3["confirmed_display_name"] is None
    assert s3["group_id"] is None
    assert s3["decision_source"] is None
    assert s3["decision_reviewed"] is False

    # DB からも消えており、GET でも確定が復活しないこと
    remaining = GitHubSkillDisplayDecisionRepository(
        client._db_session, uid
    ).get_for_user()
    assert remaining == []


def test_reset_ungroups_all_members(client) -> None:
    """グループ全メンバーの identity を渡すと畳み込みが解ける（バラす / #496）。"""
    headers = auth_header(client, "disp_reset_group")
    uid = _user_id(client, "disp_reset_group")
    # 2 つの package を同一 group_id で確定（N:1 畳み込み）
    detected = [
        DetectedSkill(
            kind="package",
            canonical_name=name,
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
                )
            ],
        )
        for name in ("@aws-sdk/client-s3", "@aws-sdk/client-eventbridge")
    ]
    GitHubSkillRepository(client._db_session, uid).replace_for_user(detected)
    GitHubSkillDisplayDecisionRepository(client._db_session, uid).upsert_many(
        [
            DisplayDecisionInput("package", "npm", "@aws-sdk/client-s3", "AWS", "grp-aws"),
            DisplayDecisionInput(
                "package", "npm", "@aws-sdk/client-eventbridge", "AWS", "grp-aws"
            ),
        ]
    )

    resp = client.request(
        "DELETE",
        "/api/github-link/skills/display-decisions",
        json={
            "identities": [
                {"kind": "package", "ecosystem": "npm", "canonical_name": "@aws-sdk/client-s3"},
                {
                    "kind": "package",
                    "ecosystem": "npm",
                    "canonical_name": "@aws-sdk/client-eventbridge",
                },
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200
    by_name = {s["canonical_name"]: s for s in resp.json()["skills"]}
    for name in ("@aws-sdk/client-s3", "@aws-sdk/client-eventbridge"):
        assert by_name[name]["confirmed_display_name"] is None
        assert by_name[name]["group_id"] is None


def test_reset_is_idempotent_for_missing_decision(client) -> None:
    """確定行が無い identity のリセットは 200・件数 0 で冪等（存在スキルなら 422 にしない）。"""
    headers = auth_header(client, "disp_reset_idem")
    uid = _user_id(client, "disp_reset_idem")
    GitHubSkillRepository(client._db_session, uid).replace_for_user(_detected())

    resp = client.request(
        "DELETE",
        "/api/github-link/skills/display-decisions",
        json={
            "identities": [
                {"kind": "package", "ecosystem": "npm", "canonical_name": "@aws-sdk/client-s3"}
            ]
        },
        headers=headers,
    )
    assert resp.status_code == 200
    by_name = {s["canonical_name"]: s for s in resp.json()["skills"]}
    assert by_name["@aws-sdk/client-s3"]["confirmed_display_name"] is None
