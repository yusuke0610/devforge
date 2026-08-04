"""経歴書ドラフトのルールベースマッピング（mapper / context）の単体テスト（ADR-0018）。

mapper は純関数として DraftSource を直接組み立てて検証する。
context（スキル証跡の反転・連携キャッシュの検証）は実 SQLite セッションで検証する
（DB モック禁止 / .claude/rules/backend/test.md）。
"""

from datetime import date

import pytest
from app.models import GitHubLinkCache, User
from app.models.skill import GitHubSkill, GitHubSkillEvidence
from app.schemas.github_link import AnalyzedRepoSummary
from app.schemas.resume import TechnologyStackItem
from app.services.agent.resume_draft.context import (
    _SELECTION_SIGNAL_KEYS,
    DraftSource,
    RepoTechnology,
    ResumeDraftNoRepositoriesError,
    ResumeDraftSourceUnavailableError,
    build_draft_source,
)
from app.services.agent.resume_draft.mapper import (
    NOISE_REASON_LEARNING_TOPIC,
    NOISE_REASON_SHORT_LIVED,
    PLACEHOLDER_COMPANY,
    PROJECT_LIMIT,
    STACK_LIMIT_PER_PROJECT,
    build_skeleton,
    evaluate_noise,
    select_repos,
)

_TODAY = date(2026, 7, 1)


def _repo(full_name: str, *, description: str = "", created: str = "2023-01-15T00:00:00Z",
          pushed: str = "2026-06-01T00:00:00Z", topics: list[str] | None = None,
          language_bytes: int = 0) -> AnalyzedRepoSummary:
    """テスト用のリポジトリサマリを生成する。"""
    return AnalyzedRepoSummary(
        full_name=full_name, description=description, created_at=created, pushed_at=pushed,
        topics=topics or [], language_bytes_total=language_bytes,
    )


def _source(repos: list, technologies: dict | None = None) -> DraftSource:
    """テスト用の DraftSource を生成する。"""
    return DraftSource(
        username="octocat",
        email="octo@example.com",
        repos=repos,
        repo_technologies=technologies or {},
    )


# ---------------------------------------------------------------------------
# select_repos: リポジトリ選定の決定論
# ---------------------------------------------------------------------------


def test_select_repos_ranks_long_lived_over_recently_touched() -> None:
    """第 1 キーは継続期間（ADR-0026 決定 3）。

    「昨日 README を直しただけのチュートリアル」が「作り込んで完成させた本命」に
    勝つのを防ぐ。直近性は主キーから外す。
    """
    source = _source(
        [
            # 3 日で終わったが昨日 push（チュートリアル型）
            _repo("o/tutorial", created="2026-06-25T00:00:00Z", pushed="2026-06-30T00:00:00Z"),
            # 2 年継続。最終 push は半年前（本命型）
            _repo("o/flagship", created="2024-01-01T00:00:00Z", pushed="2026-01-01T00:00:00Z"),
        ]
    )
    assert [r.full_name for r in select_repos(source)] == ["o/flagship", "o/tutorial"]


def test_select_repos_tiebreaks_by_language_bytes() -> None:
    """継続期間が同じなら実装量（言語バイト合計）の降順。"""
    source = _source(
        [
            _repo("o/small", language_bytes=100),
            _repo("o/big", language_bytes=9000),
            _repo("o/mid", language_bytes=3000),
        ]
    )
    assert [r.full_name for r in select_repos(source)] == ["o/big", "o/mid", "o/small"]


def test_select_repos_tiebreaks_by_pushed_at_after_bytes() -> None:
    """継続期間・実装量が同じなら最終 push が新しい方が上位（直近性は第 3 キー）。"""
    source = _source(
        [
            # 継続 365 日・実装量 500 で揃え、push 日時だけ変える
            _repo("o/stale", created="2025-01-01T00:00:00Z", pushed="2026-01-01T00:00:00Z",
                  language_bytes=500),
            _repo("o/fresh", created="2025-06-01T00:00:00Z", pushed="2026-06-01T00:00:00Z",
                  language_bytes=500),
        ]
    )
    assert [r.full_name for r in select_repos(source)] == ["o/fresh", "o/stale"]


def test_select_repos_is_totally_ordered_by_name() -> None:
    """全キー同値でも full_name の辞書順で並びが一意に決まる（完全順序）。"""
    repos = [_repo("o/c"), _repo("o/a"), _repo("o/b")]
    assert [r.full_name for r in select_repos(_source(repos))] == ["o/a", "o/b", "o/c"]
    # 入力順を変えても同じ並びになること（同一入力 → 同一出力の不変条件）
    assert [r.full_name for r in select_repos(_source(list(reversed(repos))))] == [
        "o/a", "o/b", "o/c",
    ]


def test_select_repos_treats_invalid_dates_as_zero_duration() -> None:
    """日付が不正・空でも例外にならず、継続期間 0 として下位に落ちる。"""
    source = _source(
        [
            _repo("o/broken", created="", pushed=""),
            _repo("o/invalid", created="not-a-date", pushed="2026-06-01T00:00:00Z"),
            _repo("o/valid", created="2025-01-01T00:00:00Z", pushed="2026-01-01T00:00:00Z"),
        ]
    )
    assert [r.full_name for r in select_repos(source)][0] == "o/valid"


def test_select_repos_caps_at_project_limit() -> None:
    """上限件数（PROJECT_LIMIT）で打ち切る。"""
    repos = [
        _repo(f"o/repo-{i}", created="2024-01-01T00:00:00Z",
              pushed=f"2024-0{i + 1}-01T00:00:00Z")
        for i in range(8)
    ]
    selected = select_repos(_source(repos))
    assert len(selected) == PROJECT_LIMIT
    # 継続期間が最も長いもの（最後に push されたもの）が先頭
    assert selected[0].full_name == "o/repo-7"


# ---------------------------------------------------------------------------
# evaluate_noise: デフォルト非選択の判定（ADR-0026 決定 2・3）
#
# 機械は候補を落とさない。判定はデフォルト選択状態と理由表示にのみ影響させる。
# ---------------------------------------------------------------------------


def test_evaluate_noise_flags_short_lived_repo() -> None:
    """継続期間が閾値未満なら非選択 + 理由を返す。"""
    repo = _repo("o/tutorial", created="2026-06-25T00:00:00Z", pushed="2026-06-30T00:00:00Z")
    verdict = evaluate_noise(repo)
    assert verdict.selected_by_default is False
    assert NOISE_REASON_SHORT_LIVED in verdict.reasons


def test_evaluate_noise_flags_learning_topics() -> None:
    """topics に学習用途語があれば非選択 + 理由を返す。"""
    repo = _repo("o/app", topics=["python", "tutorial"])
    verdict = evaluate_noise(repo)
    assert verdict.selected_by_default is False
    assert NOISE_REASON_LEARNING_TOPIC in verdict.reasons


def test_evaluate_noise_normalizes_topic_notation() -> None:
    """topics は小文字化 + 区切り除去して完全一致で判定する。"""
    # hands-on / Hands_On / HANDSON はいずれも学習用途語として扱う
    for topic in ("hands-on", "Hands_On", "HANDSON"):
        assert evaluate_noise(_repo("o/app", topics=[topic])).selected_by_default is False
    # 部分一致では落とさない（本命が学習用途と誤判定されるのを防ぐ）
    assert evaluate_noise(_repo("o/app", topics=["sample-api-server"])).selected_by_default


def test_evaluate_noise_returns_all_applicable_reasons() -> None:
    """複数該当なら理由を全て返す（順序も決定論）。"""
    repo = _repo(
        "o/study", created="2026-06-25T00:00:00Z", pushed="2026-06-30T00:00:00Z",
        topics=["study"],
    )
    verdict = evaluate_noise(repo)
    assert verdict.reasons == (NOISE_REASON_SHORT_LIVED, NOISE_REASON_LEARNING_TOPIC)


def test_evaluate_noise_selects_substantial_repo() -> None:
    """閾値以上かつ学習用途語なしならデフォルト選択（理由は空）。"""
    repo = _repo("o/flagship", created="2024-01-01T00:00:00Z", pushed="2026-01-01T00:00:00Z",
                 topics=["fastapi"])
    verdict = evaluate_noise(repo)
    assert verdict.selected_by_default is True
    assert verdict.reasons == ()


def test_evaluate_noise_threshold_is_inclusive_lower_bound() -> None:
    """継続期間がちょうど閾値ならデフォルト選択（閾値「未満」が非選択）。"""
    # threshold_days=30 に対し、継続 30 日 = 選択 / 29 日 = 非選択
    exactly = _repo("o/exact", created="2026-06-01T00:00:00Z", pushed="2026-07-01T00:00:00Z")
    just_under = _repo("o/under", created="2026-06-02T00:00:00Z", pushed="2026-07-01T00:00:00Z")
    assert evaluate_noise(exactly, threshold_days=30).selected_by_default is True
    assert evaluate_noise(just_under, threshold_days=30).selected_by_default is False


def test_evaluate_noise_does_not_drop_candidates() -> None:
    """ノイズ判定は select_repos の結果件数を変えない（機械は候補を落とさない）。"""
    repos = [
        _repo("o/tutorial", created="2026-06-25T00:00:00Z", pushed="2026-06-30T00:00:00Z",
              topics=["tutorial"]),
        _repo("o/flagship", created="2024-01-01T00:00:00Z", pushed="2026-01-01T00:00:00Z"),
    ]
    selected = select_repos(_source(repos))
    assert len(selected) == 2
    assert "o/tutorial" in [r.full_name for r in selected]


# ---------------------------------------------------------------------------
# build_skeleton: 骨格 payload の構築
# ---------------------------------------------------------------------------


def test_build_skeleton_top_level_and_placeholder_experience() -> None:
    """トップレベルとプレースホルダ職歴（個人開発）が契約どおり組み立てられる。"""
    source = _source(
        [
            _repo("o/first", created="2022-03-10T00:00:00Z"),
            _repo("o/second", created="2021-11-05T00:00:00Z"),
        ]
    )
    selected = select_repos(source)
    payload = build_skeleton(source, selected, today=_TODAY)

    assert payload["full_name"] == "octocat"
    assert payload["email"] == "octo@example.com"
    assert payload["github_url"] == "https://github.com/octocat"
    assert payload["career_summary"] == ""
    assert payload["self_pr"] == ""
    assert payload["qualifications"] == []

    (experience,) = payload["experiences"]
    assert experience["company"] == PLACEHOLDER_COMPANY
    assert experience["is_it_company"] is True
    assert experience["is_current"] is True
    assert experience["end_date"] == ""
    # 選定リポの最古 created_at（YYYY-MM）を職歴の開始にする
    assert experience["start_date"] == "2021-11"
    (client,) = experience["clients"]
    assert len(client["projects"]) == 2


def test_build_skeleton_project_period_current_boundary() -> None:
    """最終 push が 90 日以内なら参画中（end は空文字契約）、超えたら期間を閉じる。"""
    source = _source(
        [
            _repo("o/active", created="2024-01-01T00:00:00Z", pushed="2026-04-05T00:00:00Z"),
            _repo("o/stale", created="2024-01-01T00:00:00Z", pushed="2026-03-01T00:00:00Z"),
        ]
    )
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    projects = {p["name"]: p for p in payload["experiences"][0]["clients"][0]["projects"]}

    active_period = projects["active"]["periods"][0]
    assert active_period == {"start_date": "2024-01", "end_date": "", "is_current": True}

    stale_period = projects["stale"]["periods"][0]
    assert stale_period == {"start_date": "2024-01", "end_date": "2026-03", "is_current": False}


def test_build_skeleton_skips_period_without_created_at() -> None:
    """created_at が空のリポは期間を出さない（不正な期間を捏造しない）。"""
    source = _source([_repo("o/no-date", created="", pushed="")])
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    (project,) = payload["experiences"][0]["clients"][0]["projects"]
    assert project["periods"] == []
    # 職歴の開始も空になる
    assert payload["experiences"][0]["start_date"] == ""


def test_build_skeleton_description_falls_back_to_repo_description() -> None:
    """プロジェクト description は LLM マージ前のフォールバックとして repo description を持つ。"""
    source = _source([_repo("o/app", description="タスク管理アプリ")])
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    (project,) = payload["experiences"][0]["clients"][0]["projects"]
    assert project["description"] == "タスク管理アプリ"
    assert project["team"] == {"total": "1", "members": [{"role": "開発", "count": 1}]}
    assert project["phases"] == []


def test_build_skeleton_stacks_ordered_and_capped() -> None:
    """技術スタックはカテゴリ順（言語→FW→IaC）・量的シグナル降順で上限件数に絞る。"""
    technologies = [
        RepoTechnology("iac", "terraform-provider-aws", 0.9),
        RepoTechnology("framework", "fastapi", 0.9),
        RepoTechnology("language", "Python", 0.9, language_bytes=5000),
        RepoTechnology("language", "TypeScript", 0.9, language_bytes=9000),
    ] + [RepoTechnology("framework", f"lib-{i}", 0.5 - i * 0.01) for i in range(6)]
    source = _source([_repo("o/app")], technologies={"o/app": technologies})
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    (project,) = payload["experiences"][0]["clients"][0]["projects"]

    stacks = project["technology_stacks"]
    assert len(stacks) == STACK_LIMIT_PER_PROJECT
    # 言語がバイト数降順で先頭に並ぶ
    assert stacks[0] == {"category": "language", "name": "TypeScript"}
    assert stacks[1] == {"category": "language", "name": "Python"}
    # framework は confidence 降順（fastapi 0.9 が先頭）
    assert stacks[2] == {"category": "framework", "name": "fastapi"}
    # 各カテゴリが保存契約（schemas/resume.py の Literal）に収まる
    for stack in stacks:
        TechnologyStackItem.model_validate(stack)


# ---------------------------------------------------------------------------
# context: 連携キャッシュの検証とスキル証跡の反転（実 SQLite）
# ---------------------------------------------------------------------------


def _create_user(db_session) -> User:
    """テスト用ユーザーを作成して返す。"""
    user = User(username="octocat", email="octo@example.com")
    db_session.add(user)
    db_session.commit()
    return user


def _cache_result(repos: list[dict] | None) -> dict:
    """連携キャッシュの result JSON を生成する（repos=None で旧形式を再現）。"""
    result: dict = {
        "username": "octocat",
        "repos_analyzed": 1,
        "unique_skills": 1,
        "analyzed_at": "2026-06-01T00:00:00",
        "languages": {"Python": 1000},
    }
    if repos is not None:
        result["repos"] = repos
    return result


def _repo_summary(**overrides) -> dict:
    """新形式（ADR-0026 決定 4）のリポジトリサマリ JSON を生成する。

    選定シグナル（topics 以下）を含む。旧形式を再現したいテストは
    ``_repo_summary()`` から当該キーを del して使う。
    """
    summary = {
        "full_name": "octocat/app",
        "description": "アプリ",
        "created_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2026-06-01T00:00:00Z",
        "topics": ["fastapi"],
        "language_bytes_total": 12000,
        "direct_dependency_count": 3,
        "ecosystem_count": 1,
        "has_infra": True,
    }
    summary.update(overrides)
    return summary


def _add_skill(db_session, user_id: str, *, kind: str, name: str, evidence: list[dict]) -> None:
    """スキル + 証跡を直接投入する。"""
    skill = GitHubSkill(user_id=user_id, kind=kind, canonical_name=name)
    skill.evidence = [GitHubSkillEvidence(**ev) for ev in evidence]
    db_session.add(skill)
    db_session.commit()


def test_build_draft_source_requires_completed_cache(db_session) -> None:
    """キャッシュ無し・未完了はドラフト入力を組み立てられない。"""
    user = _create_user(db_session)
    with pytest.raises(ResumeDraftSourceUnavailableError):
        build_draft_source(db_session, user)

    db_session.add(GitHubLinkCache(user_id=user.id, status="processing", result=None))
    db_session.commit()
    with pytest.raises(ResumeDraftSourceUnavailableError):
        build_draft_source(db_session, user)


def test_build_draft_source_rejects_legacy_cache_without_repos(db_session) -> None:
    """ADR-0018 以前の旧形式キャッシュ（repos キー無し）は再連携が必要。"""
    user = _create_user(db_session)
    db_session.add(
        GitHubLinkCache(user_id=user.id, status="completed", result=_cache_result(repos=None))
    )
    db_session.commit()
    with pytest.raises(ResumeDraftSourceUnavailableError):
        build_draft_source(db_session, user)


def test_build_draft_source_rejects_empty_repos_as_no_repositories(db_session) -> None:
    """新形式で repos が空リスト（分析対象 0 件）は旧形式と区別され、専用例外になる。"""
    user = _create_user(db_session)
    db_session.add(
        GitHubLinkCache(user_id=user.id, status="completed", result=_cache_result(repos=[]))
    )
    db_session.commit()
    # 0 件は旧形式（再連携で回復）ではなく NoRepositories（リポジトリ追加が必要）
    with pytest.raises(ResumeDraftNoRepositoriesError):
        build_draft_source(db_session, user)


def test_build_draft_source_rejects_cache_without_selection_signals(db_session) -> None:
    """ADR-0026 より前のキャッシュ（選定シグナル無し）は再連携が必要。

    スキーマ側は既定値を持つのでパース自体は通ってしまう。生 JSON のキー有無で
    判別して 409 導線に倒していることを確認する。
    """
    user = _create_user(db_session)
    legacy = _repo_summary()
    for key in _SELECTION_SIGNAL_KEYS:
        del legacy[key]
    # スキーマは旧形式 JSON を既定値で受理する（後方互換）
    assert AnalyzedRepoSummary.model_validate(legacy).language_bytes_total == 0

    db_session.add(
        GitHubLinkCache(user_id=user.id, status="completed", result=_cache_result(repos=[legacy]))
    )
    db_session.commit()
    # NoRepositories ではなく「再連携で回復する」側の例外になること
    with pytest.raises(ResumeDraftSourceUnavailableError) as exc:
        build_draft_source(db_session, user)
    assert not isinstance(exc.value, ResumeDraftNoRepositoriesError)


@pytest.mark.parametrize("missing_key", sorted(_SELECTION_SIGNAL_KEYS))
def test_build_draft_source_rejects_cache_missing_any_signal(db_session, missing_key) -> None:
    """シグナルが 1 つでも欠けたキャッシュは旧形式として扱う。

    代表キーだけを見ると「一部のシグナルだけ持つキャッシュ」を取りこぼし、
    Pydantic の既定値で欠落を埋めたまま選定が走ってしまう。
    """
    user = _create_user(db_session)
    partial = _repo_summary()
    del partial[missing_key]
    db_session.add(
        GitHubLinkCache(user_id=user.id, status="completed", result=_cache_result(repos=[partial]))
    )
    db_session.commit()
    with pytest.raises(ResumeDraftSourceUnavailableError):
        build_draft_source(db_session, user)


def test_build_draft_source_rejects_cache_with_partially_migrated_repos(db_session) -> None:
    """1 件でもシグナル無しが混ざれば旧形式として扱う（選定が偏るのを防ぐ）。"""
    user = _create_user(db_session)
    legacy = _repo_summary(full_name="octocat/legacy")
    del legacy["language_bytes_total"]
    db_session.add(
        GitHubLinkCache(
            user_id=user.id,
            status="completed",
            result=_cache_result(repos=[_repo_summary(), legacy]),
        )
    )
    db_session.commit()
    with pytest.raises(ResumeDraftSourceUnavailableError):
        build_draft_source(db_session, user)


def test_build_draft_source_keeps_selection_signals(db_session) -> None:
    """新形式のシグナルが DraftSource までそのまま渡ること（#562 / #564 の入力）。"""
    user = _create_user(db_session)
    db_session.add(
        GitHubLinkCache(
            user_id=user.id,
            status="completed",
            result=_cache_result(repos=[_repo_summary()]),
        )
    )
    db_session.commit()

    repo = build_draft_source(db_session, user).repos[0]
    assert repo.topics == ["fastapi"]
    assert repo.language_bytes_total == 12000
    assert repo.direct_dependency_count == 3
    assert repo.ecosystem_count == 1
    assert repo.has_infra is True


def test_build_draft_source_inverts_skill_evidence(db_session) -> None:
    """スキル証跡が「リポ → 技術」に反転され、採用基準どおりフィルタされる。"""
    user = _create_user(db_session)
    repo_summary = _repo_summary()
    db_session.add(
        GitHubLinkCache(
            user_id=user.id, status="completed", result=_cache_result(repos=[repo_summary])
        )
    )
    db_session.commit()

    _add_skill(
        db_session, user.id, kind="language", name="Python",
        evidence=[{
            "repo_full_name": "octocat/app", "signal_source": "language_bytes",
            "confidence": 0.9, "language_bytes": 1234,
        }],
    )
    # direct 宣言 + 実 import の二重証跡 → confidence の大きい方に畳まれる
    _add_skill(
        db_session, user.id, kind="package", name="fastapi",
        evidence=[
            {"repo_full_name": "octocat/app", "signal_source": "manifest_declared",
             "confidence": 0.6, "dependency_kind": "direct"},
            {"repo_full_name": "octocat/app", "signal_source": "actual_import",
             "confidence": 0.8, "dependency_kind": "direct"},
        ],
    )
    # 間接依存（direct でも actual_import でもない）→ 採用しない
    _add_skill(
        db_session, user.id, kind="package", name="urllib3",
        evidence=[{
            "repo_full_name": "octocat/app", "signal_source": "manifest_declared",
            "confidence": 0.3, "dependency_kind": "indirect",
        }],
    )
    _add_skill(
        db_session, user.id, kind="infra", name="aws",
        evidence=[{
            "repo_full_name": "octocat/app", "signal_source": "infra_declared",
            "confidence": 0.7,
        }],
    )

    source = build_draft_source(db_session, user)
    assert source.username == "octocat"
    assert [r.full_name for r in source.repos] == ["octocat/app"]

    technologies = {
        (t.category, t.name): t for t in source.repo_technologies["octocat/app"]
    }
    assert set(technologies) == {
        ("language", "Python"), ("framework", "fastapi"), ("iac", "aws"),
    }
    assert technologies[("language", "Python")].language_bytes == 1234
    assert technologies[("framework", "fastapi")].confidence == 0.8
