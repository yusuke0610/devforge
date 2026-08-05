"""経歴書ドラフトのルールベースマッピング（mapper / context）の単体テスト（ADR-0018）。

mapper は純関数として DraftSource を直接組み立てて検証する。
context（スキル証跡の反転・連携キャッシュの検証）は実 SQLite セッションで検証する
（DB モック禁止 / .claude/rules/backend/test.md）。
"""

import json
from datetime import date

import pytest
from app.models import GitHubLinkCache, User
from app.models.skill import GitHubSkill, GitHubSkillEvidence
from app.schemas.github_link import AnalyzedRepoSummary
from app.schemas.resume import Project, TechnologyStackItem
from app.services.agent.resume_draft import mapper
from app.services.agent.resume_draft.context import (
    _SELECTION_SIGNAL_KEYS,
    DraftSource,
    RepoTechnology,
    ResumeDraftNoRepositoriesError,
    ResumeDraftSourceUnavailableError,
    build_draft_source,
)
from app.services.agent.resume_draft.mapper import (
    MIN_DURATION_DAYS,
    PROJECT_LIMIT,
    REASON_LEARNING_TOPIC,
    REASON_SHORT_DURATION,
    STACK_LIMIT_PER_PROJECT,
    UnknownRepositoryError,
    build_candidates,
    build_pdf_payload,
    build_skeleton,
    evaluate_default_selection,
    rank_repos,
    select_repos,
    select_requested_repos,
    selection_score,
)

_TODAY = date(2026, 7, 1)


def _repo(full_name: str, *, description: str = "", created: str = "2023-01-15T00:00:00Z",
          pushed: str = "2026-06-01T00:00:00Z", topics: list[str] | None = None,
          language_bytes_total: int = 10_000, direct_dependency_count: int = 0,
          ecosystem_count: int = 0, has_infra: bool = False) -> AnalyzedRepoSummary:
    """テスト用のリポジトリサマリを生成する。"""
    return AnalyzedRepoSummary(
        full_name=full_name,
        description=description,
        created_at=created,
        pushed_at=pushed,
        topics=topics or [],
        language_bytes_total=language_bytes_total,
        direct_dependency_count=direct_dependency_count,
        ecosystem_count=ecosystem_count,
        has_infra=has_infra,
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


def test_rank_repos_prefers_long_running_over_recently_pushed() -> None:
    """主キーは「継続期間 × 実装量」。直近 push だけの短命リポは上に来ない（ADR-0026 決定 3）。

    昨日 README を直しただけのチュートリアル（継続 1 日）より、半年作り込んで
    半年前に止まった本命（継続 180 日）が優先される。
    """
    source = _source(
        [
            _repo(
                "o/tutorial-yesterday",
                created="2026-06-29T00:00:00Z",
                pushed="2026-06-30T00:00:00Z",
                language_bytes_total=50_000,
            ),
            _repo(
                "o/real-project",
                created="2024-06-01T00:00:00Z",
                pushed="2024-11-28T00:00:00Z",
                language_bytes_total=50_000,
            ),
        ]
    )
    assert [r.full_name for r in rank_repos(source)] == ["o/real-project", "o/tutorial-yesterday"]


def test_rank_repos_prefers_larger_implementation_at_equal_duration() -> None:
    """継続期間が同じなら実装量（言語バイト合計）の多い方が上。"""
    source = _source(
        [
            _repo("o/small", language_bytes_total=1_000),
            _repo("o/big", language_bytes_total=900_000),
        ]
    )
    assert [r.full_name for r in rank_repos(source)] == ["o/big", "o/small"]


def test_selection_score_counts_dependency_and_infra_signals() -> None:
    """実装量には依存の厚み・エコシステム数・IaC 宣言もバイト相当で加算される。"""
    plain = _repo("o/plain", language_bytes_total=10_000)
    rich = _repo(
        "o/rich",
        language_bytes_total=10_000,
        direct_dependency_count=20,
        ecosystem_count=2,
        has_infra=True,
    )
    assert selection_score(rich) > selection_score(plain)


def test_rank_repos_tiebreaks_by_pushed_at_then_full_name() -> None:
    """スコアが同点なら直近性（pushed_at 降順）、それも同じなら full_name 昇順。

    直近性は主キーからタイブレークへ降格した（ADR-0026 決定 3）。
    """
    # 継続期間（ともに 181 日）と実装量を揃えてスコアを同点にする
    source = _source(
        [
            _repo("o/b-old", created="2025-01-01T00:00:00Z", pushed="2025-07-01T00:00:00Z"),
            _repo("o/b-new", created="2025-02-01T00:00:00Z", pushed="2025-08-01T00:00:00Z"),
            _repo("o/a-old", created="2025-01-01T00:00:00Z", pushed="2025-07-01T00:00:00Z"),
        ]
    )
    assert [r.full_name for r in rank_repos(source)] == ["o/b-new", "o/a-old", "o/b-old"]


def test_rank_repos_is_a_total_order_independent_of_input_order() -> None:
    """同一集合なら入力順に関わらず並びが一意に決まる（完全順序の不変条件）。"""
    repos = [
        _repo("o/a", created="2024-01-01T00:00:00Z", pushed="2024-07-01T00:00:00Z"),
        _repo("o/b", created="2024-01-01T00:00:00Z", pushed="2024-07-01T00:00:00Z"),
        _repo("o/c", created="2024-01-01T00:00:00Z", pushed="2024-07-01T00:00:00Z"),
        _repo("o/d", created="2020-01-01T00:00:00Z", pushed="2026-01-01T00:00:00Z"),
    ]
    expected = [r.full_name for r in rank_repos(_source(repos))]
    assert [r.full_name for r in rank_repos(_source(list(reversed(repos))))] == expected
    assert [r.full_name for r in rank_repos(_source([repos[2], repos[0], repos[3], repos[1]]))] == (
        expected
    )


def test_rank_repos_keeps_all_candidates() -> None:
    """機械は候補を落とさない（ADR-0026 決定 2）。順位付けだけで件数は減らさない。"""
    repos = [_repo(f"o/repo-{i}", language_bytes_total=(i + 1) * 1000) for i in range(8)]
    assert len(rank_repos(_source(repos))) == 8


def test_rank_repos_handles_invalid_dates_without_crashing() -> None:
    """created_at / pushed_at が空・不正でも継続期間 0 として順位付けできる。"""
    source = _source(
        [
            _repo("o/broken", created="", pushed=""),
            _repo("o/normal", created="2024-01-01T00:00:00Z", pushed="2025-01-01T00:00:00Z"),
        ]
    )
    assert [r.full_name for r in rank_repos(source)] == ["o/normal", "o/broken"]


def test_select_repos_caps_at_project_limit() -> None:
    """select_repos は順位付けの上位を上限件数（PROJECT_LIMIT）で打ち切る。"""
    repos = [_repo(f"o/repo-{i}", language_bytes_total=(i + 1) * 1000) for i in range(8)]
    source = _source(repos)
    selected = select_repos(source)
    assert len(selected) == PROJECT_LIMIT
    assert [r.full_name for r in selected] == [
        r.full_name for r in rank_repos(source)[:PROJECT_LIMIT]
    ]


# ---------------------------------------------------------------------------
# build_candidates / select_requested_repos: 候補提示と人間の採用（ADR-0026 決定 2）
# ---------------------------------------------------------------------------


def test_build_candidates_returns_every_repo_in_rank_order() -> None:
    """入口フィルタを通った候補は全件返る。並びは rank_repos と一致する。"""
    source = _source(
        [
            _repo("o/tutorial", created="2026-06-01T00:00:00Z", pushed="2026-06-02T00:00:00Z",
                  topics=["tutorial"]),
            _repo("o/real", created="2024-01-01T00:00:00Z", pushed="2025-01-01T00:00:00Z"),
        ]
    )
    candidates = build_candidates(source)
    assert [c.full_name for c in candidates] == [r.full_name for r in rank_repos(source)]
    assert len(candidates) == 2


def test_build_candidates_carries_signals_and_default_selection() -> None:
    """候補はシグナル（継続期間・実装量・IaC・技術スタック）と選択状態・理由を持つ。"""
    source = _source(
        [
            _repo(
                "o/real", description="タスク管理アプリ",
                created="2024-01-01T00:00:00Z", pushed="2025-01-01T00:00:00Z",
                language_bytes_total=12_000, has_infra=True,
            )
        ],
        technologies={"o/real": [RepoTechnology("language", "Python", 0.9, language_bytes=12_000)]},
    )
    (candidate,) = build_candidates(source)

    assert candidate.full_name == "o/real"
    assert candidate.description == "タスク管理アプリ"
    assert candidate.duration_days == 366
    assert candidate.implementation_volume == 12_000 + mapper.INFRA_VOLUME_WEIGHT
    assert candidate.has_infra is True
    assert candidate.technology_stacks == [{"category": "language", "name": "Python"}]
    assert candidate.default_selected is True
    assert candidate.reasons == ()


def test_build_candidates_marks_noise_without_dropping_it() -> None:
    """ノイズ判定は候補から落とさず、デフォルト非選択 + 理由で表現する。"""
    source = _source(
        [_repo("o/tutorial", created="2026-06-01T00:00:00Z", pushed="2026-06-02T00:00:00Z",
               topics=["tutorial"])]
    )
    (candidate,) = build_candidates(source)
    assert candidate.default_selected is False
    assert candidate.reasons == (REASON_SHORT_DURATION, REASON_LEARNING_TOPIC)


def test_select_requested_repos_returns_rank_order_regardless_of_request_order() -> None:
    """採用リポジトリは要求順ではなく順位順に解決する（生成物の並びを決定論に保つ）。"""
    source = _source(
        [
            _repo("o/small", language_bytes_total=1_000),
            _repo("o/big", language_bytes_total=900_000),
        ]
    )
    selected = select_requested_repos(source, ["o/small", "o/big"])
    assert [r.full_name for r in selected] == ["o/big", "o/small"]


def test_select_requested_repos_deduplicates() -> None:
    """同じリポジトリを重複指定しても 1 件に畳む。"""
    source = _source([_repo("o/app")])
    assert len(select_requested_repos(source, ["o/app", "o/app"])) == 1


def test_select_requested_repos_rejects_unknown_repository() -> None:
    """連携データに無いリポジトリの指定は拒否する（捏造リポの混入を防ぐ）。"""
    source = _source([_repo("o/app")])
    with pytest.raises(UnknownRepositoryError):
        select_requested_repos(source, ["o/app", "o/ghost"])


# ---------------------------------------------------------------------------
# evaluate_default_selection: デフォルト選択状態とその理由（ADR-0026 決定 3）
# ---------------------------------------------------------------------------


def test_default_selection_selects_long_running_repo() -> None:
    """継続期間が閾値以上で学習用途 topics も無ければデフォルト選択・理由なし。"""
    repo = _repo(
        "o/real", created="2024-01-01T00:00:00Z", pushed="2025-01-01T00:00:00Z",
        topics=["fastapi", "resume"],
    )
    verdict = evaluate_default_selection(repo)
    assert verdict.selected is True
    assert verdict.reasons == ()


def test_default_selection_flags_short_duration() -> None:
    """継続期間が閾値未満ならデフォルト非選択 + 理由。"""
    repo = _repo("o/quick", created="2026-06-01T00:00:00Z", pushed="2026-06-03T00:00:00Z")
    verdict = evaluate_default_selection(repo)
    assert verdict.selected is False
    assert verdict.reasons == (REASON_SHORT_DURATION,)


def test_default_selection_duration_threshold_boundary() -> None:
    """閾値ちょうどは選択、1 日足りなければ非選択（境界の固定）。"""
    exactly = _repo(
        "o/exact", created="2026-01-01T00:00:00Z",
        pushed=f"2026-01-{1 + MIN_DURATION_DAYS:02d}T00:00:00Z",
    )
    one_short = _repo(
        "o/short", created="2026-01-01T00:00:00Z",
        pushed=f"2026-01-{MIN_DURATION_DAYS:02d}T00:00:00Z",
    )
    assert evaluate_default_selection(exactly).selected is True
    assert evaluate_default_selection(one_short).selected is False


def test_default_selection_threshold_is_injectable() -> None:
    """閾値はテストから注入できる（build_skeleton(today=...) と同じ流儀）。"""
    repo = _repo("o/quick", created="2026-06-01T00:00:00Z", pushed="2026-06-03T00:00:00Z")
    assert evaluate_default_selection(repo, min_duration_days=2).selected is True


@pytest.mark.parametrize(
    "topic",
    ["tutorial", "Tutorial", "TUTORIAL", "react-tutorial", "study_group", "hands-on", "Learning"],
)
def test_default_selection_flags_learning_topics(topic: str) -> None:
    """学習用途 topics は大文字小文字・区切り文字を正規化して判定する。"""
    repo = _repo(
        "o/learn", created="2024-01-01T00:00:00Z", pushed="2025-01-01T00:00:00Z",
        topics=[topic],
    )
    verdict = evaluate_default_selection(repo)
    assert verdict.selected is False
    assert verdict.reasons == (REASON_LEARNING_TOPIC,)


@pytest.mark.parametrize("topic", ["resample", "samples-api-gateway-tools", "restudy"])
def test_default_selection_does_not_match_topic_substrings(topic: str) -> None:
    """語の一部に含まれるだけでは学習用途と判定しない（部分一致で誤爆させない）。

    ``samples-api-gateway-tools`` は語 ``samples`` を含むため判定対象だが、
    ``resample`` / ``restudy`` は別語なので対象外。
    """
    repo = _repo(
        "o/app", created="2024-01-01T00:00:00Z", pushed="2025-01-01T00:00:00Z", topics=[topic],
    )
    expected_flagged = topic == "samples-api-gateway-tools"
    assert evaluate_default_selection(repo).selected is not expected_flagged


def test_default_selection_reports_all_reasons_in_stable_order() -> None:
    """理由が複数該当する場合は決定論的な順序で全件返す。"""
    repo = _repo(
        "o/noise", created="2026-06-01T00:00:00Z", pushed="2026-06-03T00:00:00Z",
        topics=["tutorial"],
    )
    verdict = evaluate_default_selection(repo)
    assert verdict.selected is False
    assert verdict.reasons == (REASON_SHORT_DURATION, REASON_LEARNING_TOPIC)


def test_default_selection_does_not_drop_candidates_from_ranking() -> None:
    """非選択判定は候補一覧から落とさない（ADR-0026 決定 2 の不変条件）。"""
    noise = _repo("o/tutorial", created="2026-06-01T00:00:00Z", pushed="2026-06-02T00:00:00Z",
                  topics=["tutorial"])
    real = _repo("o/real", created="2024-01-01T00:00:00Z", pushed="2025-01-01T00:00:00Z")
    ranked = rank_repos(_source([noise, real]))
    assert {r.full_name for r in ranked} == {"o/tutorial", "o/real"}


# ---------------------------------------------------------------------------
# build_skeleton: 骨格 payload の構築
# ---------------------------------------------------------------------------


def test_build_skeleton_returns_projects_without_experiences() -> None:
    """出力単位は project 明細のリスト。experience は生成しない（ADR-0026 決定 1）。"""
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
    # career_summary / self_pr は experiences から独立した候補として返る（LLM が埋める）
    assert payload["career_summary"] == ""
    assert payload["self_pr"] == ""
    # 会社・事業内容・在籍期間・顧客は GitHub から得られないため生成しない
    assert "experiences" not in payload
    assert len(payload["projects"]) == 2


def test_build_skeleton_generates_no_placeholder_values() -> None:
    """生成 payload にプレースホルダ文字列が一切含まれない（ADR-0026 決定 1 の完了条件）。"""
    source = _source([_repo("o/app", description="タスク管理アプリ")])
    payload = build_skeleton(source, select_repos(source), today=_TODAY)

    serialized = json.dumps(payload, ensure_ascii=False)
    for placeholder in ("個人開発", "GitHub 上での個人開発活動", "開発（個人開発）"):
        assert placeholder not in serialized
    # 廃止した定数がモジュールに残っていないこと（再導入の抑止）
    for removed in ("PLACEHOLDER_COMPANY", "PLACEHOLDER_BUSINESS_DESCRIPTION", "PLACEHOLDER_ROLE"):
        assert not hasattr(mapper, removed)


def test_build_skeleton_leaves_human_only_fields_empty() -> None:
    """role / phases / team は生成しない（空 = 人間が埋める / ADR-0026 決定 1）。"""
    source = _source([_repo("o/app", description="タスク管理アプリ")])
    (project,) = build_skeleton(source, select_repos(source), today=_TODAY)["projects"]

    assert project["role"] == ""
    assert project["phases"] == []
    assert project["team"] == {"total": "", "members": []}
    # 保存契約（schemas/resume.py）に収まること
    Project.model_validate(project)


def test_build_skeleton_project_period_current_boundary() -> None:
    """最終 push が 90 日以内なら参画中（end は空文字契約）、超えたら期間を閉じる。"""
    source = _source(
        [
            _repo("o/active", created="2024-01-01T00:00:00Z", pushed="2026-04-05T00:00:00Z"),
            _repo("o/stale", created="2024-01-01T00:00:00Z", pushed="2026-03-01T00:00:00Z"),
        ]
    )
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    projects = {p["name"]: p for p in payload["projects"]}

    active_period = projects["active"]["periods"][0]
    assert active_period == {"start_date": "2024-01", "end_date": "", "is_current": True}

    stale_period = projects["stale"]["periods"][0]
    assert stale_period == {"start_date": "2024-01", "end_date": "2026-03", "is_current": False}


def test_build_skeleton_skips_period_without_created_at() -> None:
    """created_at が空のリポは期間を出さない（不正な期間を捏造しない）。"""
    source = _source([_repo("o/no-date", created="", pushed="")])
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    (project,) = payload["projects"]
    assert project["periods"] == []


def test_build_skeleton_description_falls_back_to_repo_description() -> None:
    """プロジェクト description は LLM マージ前のフォールバックとして repo description を持つ。"""
    source = _source([_repo("o/app", description="タスク管理アプリ")])
    payload = build_skeleton(source, select_repos(source), today=_TODAY)
    (project,) = payload["projects"]
    assert project["description"] == "タスク管理アプリ"


def test_build_pdf_payload_wraps_projects_in_empty_experience() -> None:
    """PDF レンダリング用に空の experience / client で包む（値は捏造しない）。"""
    source = _source([_repo("o/app", description="タスク管理アプリ")])
    draft = build_skeleton(source, select_repos(source), today=_TODAY)

    payload = build_pdf_payload(draft)
    assert payload["career_summary"] == draft["career_summary"]
    (experience,) = payload["experiences"]
    assert experience["company"] == ""
    assert experience["business_description"] == ""
    (client,) = experience["clients"]
    assert client["name"] == ""
    assert [p["name"] for p in client["projects"]] == ["app"]
    # 元のドラフトを破壊しない（同じ payload を PDF と JSON 双方で使うため）
    assert "experiences" not in draft


def test_build_pdf_payload_without_projects_has_no_experience() -> None:
    """プロジェクトが 0 件なら空の職歴も作らない（空箱だけの PDF を出さない）。"""
    payload = build_pdf_payload(build_skeleton(_source([]), [], today=_TODAY))
    assert payload["experiences"] == []


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
    (project,) = payload["projects"]

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
