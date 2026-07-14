"""
GitHub 連携 API エンドポイント。

POST /api/github-link/run        — GitHub 連携パイプラインをバックグラウンド実行（202）
GET  /api/github-link/cache      — 保存済みの連携結果を取得
GET  /api/github-link/cache/status — 連携ステータスポーリング用
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from ...core.errors import ErrorCode, raise_app_error, resolve_async_error_code
from ...core.messages import get_error
from ...core.security.auth import get_current_user, require_github_user
from ...core.security.dependencies import limiter
from ...db import get_db
from ...models import User
from ...repositories.github_link import GitHubLinkCacheRepository
from ...repositories.skill import (
    DisplayDecisionInput,
    GitHubSkillDisplayDecisionRepository,
    GitHubSkillRepository,
)
from ...schemas.github_link import (
    CachedGitHubLinkResponse,
    GitHubLinkRequest,
    GitHubLinkResponse,
    ProgressResponse,
)
from ...schemas.github_skill import (
    GitHubSkillsResponse,
    SkillDisplayConfirmRequest,
    SkillDisplayProposedGroup,
    SkillDisplayProposeRequest,
    SkillDisplayProposeResponse,
    SkillIdentityRef,
)
from ...schemas.shared import TaskAcceptedResponse, TaskStatusResponse
from ...services.agent.chat_service import AgentResponseParseError
from ...services.agent.llm.base import LLMError
from ...services.agent.skill_display import (
    MAX_SKILLS_PER_PROPOSAL,
    SkillForProposal,
    propose_skill_display_names,
)
from ...services.billing import credit_service
from ...services.billing.credit_service import InsufficientCreditsError
from ...services.intelligence.github_link_service import get_or_create_github_link_cache
from ...services.intelligence.skills.types import SKILL_KIND_LANGUAGE
from ...services.tasks import AsyncTaskCacheService, TaskType
from ._responses import to_skill_item

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github-link", tags=["github-link"])


def _raise_dispatch_failed() -> None:
    """タスクのディスパッチに失敗したときの 500 エラーを送出する。"""
    raise_app_error(
        status_code=500,
        code=ErrorCode.INTERNAL_ERROR,
        message=get_error("task.dispatch_failed"),
        action="しばらく待ってから再試行してください",
    )


@router.get("/cache", response_model=CachedGitHubLinkResponse)
def get_cache(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """保存済みの連携結果を取得する。"""
    cache = GitHubLinkCacheRepository(db).get_by_user(user.id)
    if not cache:
        return CachedGitHubLinkResponse()
    # cache.result は GitHubLinkResponse(...).model_dump() を保存した JSON（dict | None）。
    # Pydantic v2 は dict を受け取ると検証済みモデルへコアース可能なので validate で型を絞る。
    result = (
        GitHubLinkResponse.model_validate(cache.result) if cache.result is not None else None
    )
    return CachedGitHubLinkResponse(
        result=result,
        status=cache.status,
        error_message=cache.error_message,
        error_code=resolve_async_error_code(cache.error_message),
        warning_message=cache.warning_message,
    )


@router.get("/progress", response_model=ProgressResponse)
async def get_link_progress(
    user: User = Depends(get_current_user),
):
    """GitHub 連携タスクの進捗を取得する（ポーリング用）。

    Redis にデータがない場合（タスク未開始・Redis 障害）は step_index=0 のデフォルトを返す。
    """
    from ...services.progress_service import get_progress

    data = await get_progress(user.id)
    return ProgressResponse(**data)


def _build_skills_response(db: Session, user_id: str) -> GitHubSkillsResponse:
    """スキル（Layer 1-2）に表示名確定（Layer 3 / D11）を突き合わせてレスポンスを組む。

    確定は安定 identity（kind + ecosystem + canonical_name）で紐づける。連携の洗い替えで
    スキルが消えれば当該確定はレスポンスに現れないが、DB からは消えないため再連携で復活する。
    """
    skills = GitHubSkillRepository(db, user_id).list_for_user()
    decisions = {
        (d.kind, d.ecosystem, d.canonical_name): d
        for d in GitHubSkillDisplayDecisionRepository(db, user_id).get_for_user()
    }
    return GitHubSkillsResponse(
        skills=[
            to_skill_item(s, decisions.get((s.kind, s.ecosystem, s.canonical_name)))
            for s in skills
        ]
    )


@router.get("/skills", response_model=GitHubSkillsResponse)
def get_skills(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """GitHub 連携で推論した 3 層スキル（ADR-0016）を取得する。

    表示名の human-in-the-loop 確定（D11）があれば ``confirmed_display_name`` / ``group_id``
    として載せる。連携がまだ実行されていない場合は空配列を返す。
    """
    return _build_skills_response(db, user.id)


@router.post(
    "/skills/display-names/propose", response_model=SkillDisplayProposeResponse
)
@limiter.limit("5/minute")
async def propose_skill_display_names_endpoint(
    request: Request,
    body: SkillDisplayProposeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkillDisplayProposeResponse:
    """検出済みスキルの表示名・畳み込みグループを agent に提案させる（ADR-0016 D11）。

    agent は提案するだけで確定・DB 更新はしない（D8 / P4）。提案結果はレスポンスとして返し、
    ユーザーがレビュー・編集して ``PUT /skills/display-decisions`` で確定する。
    外部 LLM を呼ぶ高コスト endpoint のため rate limit を付与し、課金はチャットと同一契約。
    """
    # 有料モデルは LLM を呼ぶ前に残高をチェックする（事後減算 / ADR-0012）
    try:
        credit_service.ensure_can_use_model(db, user.id, body.model)
    except InsufficientCreditsError:
        raise_app_error(
            status_code=402,
            code=ErrorCode.INSUFFICIENT_CREDITS,
            message=get_error("billing.insufficient_credits"),
        )

    skills = GitHubSkillRepository(db, user.id).list_for_user()
    # language は Linguist の canonical / 表示補正で十分に読めるため提案対象外とする。
    # 畳み込み・表示名整形の価値は package（例: @aws-sdk/*）と infra（例: aws_s3_bucket）に
    # 集中しており、language を混ぜると入力が肥大してモデルが構造化出力を壊しやすい（ADR-0016 D11）。
    candidates = [s for s in skills if s.kind != SKILL_KIND_LANGUAGE]
    if not candidates:
        raise_app_error(
            status_code=404,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("agent.skill_display_no_skills"),
            action="サイドバーの「GitHub連携」から連携を実行してください",
        )
    # 送信トークン・enum サイズを抑えるため evidence の多い順に上限で絞る（ロングテールは対象外）
    sorted_skills = sorted(candidates, key=lambda s: len(s.evidence), reverse=True)
    proposal_inputs = [
        SkillForProposal(
            kind=s.kind,
            ecosystem=s.ecosystem,
            canonical_name=s.canonical_name,
            machine_display_name=s.display_name,
            parent=s.parent,
        )
        for s in sorted_skills[:MAX_SKILLS_PER_PROPOSAL]
    ]

    try:
        result = await propose_skill_display_names(body.model, proposal_inputs)
    except LLMError as exc:
        # 消費済みトークンがあれば課金してから 502（課金漏れ防止 / ADR-0012）
        if exc.usage is not None:
            try:
                credit_service.record_usage_after_llm(db, user.id, exc.usage)
            except Exception:
                logger.error("表示名提案の LLM 失敗時のクレジット記録に失敗", exc_info=True)
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_LLM_ERROR,
            message=get_error("agent.llm_failed"),
        )
    except AgentResponseParseError as exc:
        if exc.usage is not None:
            try:
                credit_service.record_usage_after_llm(db, user.id, exc.usage)
            except Exception:
                logger.error("表示名提案のパース失敗時のクレジット記録に失敗", exc_info=True)
        raise_app_error(
            status_code=502,
            code=ErrorCode.AGENT_PARSE_ERROR,
            message=get_error("agent.parse_failed"),
        )

    credit_service.record_usage_after_llm(
        db, user.id, result.usage, description=f"スキル表示名提案（{body.model}）"
    )
    return SkillDisplayProposeResponse(
        groups=[
            SkillDisplayProposedGroup(
                display_name=group.display_name,
                members=[
                    SkillIdentityRef(
                        kind=m.kind,
                        ecosystem=m.ecosystem,
                        canonical_name=m.canonical_name,
                    )
                    for m in group.members
                ],
            )
            for group in result.groups
        ]
    )


@router.put("/skills/display-decisions", response_model=GitHubSkillsResponse)
def confirm_skill_display_decisions(
    body: SkillDisplayConfirmRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GitHubSkillsResponse:
    """レビュー済みの表示名・畳み込みを確定・永続化する（ADR-0016 D11）。

    確定対象の identity は当該ユーザーの検出済みスキルに属していなければならない
    （他者・非実在 identity の混入を拒否）。確定は独立 Layer 3 テーブルへ upsert され、
    連携の洗い替えに耐える。確定後の最新スキル一覧を返す。
    """
    skills = GitHubSkillRepository(db, user.id).list_for_user()
    valid_identities = {(s.kind, s.ecosystem, s.canonical_name) for s in skills}
    for decision in body.decisions:
        if (decision.kind, decision.ecosystem, decision.canonical_name) not in valid_identities:
            raise_app_error(
                status_code=422,
                code=ErrorCode.VALIDATION_ERROR,
                message=get_error("agent.skill_display_invalid_identity"),
            )

    GitHubSkillDisplayDecisionRepository(db, user.id).upsert_many(
        [
            DisplayDecisionInput(
                kind=d.kind,
                ecosystem=d.ecosystem,
                canonical_name=d.canonical_name,
                display_name=d.display_name,
                group_id=d.group_id,
                source=d.source,
            )
            for d in body.decisions
        ]
    )
    return _build_skills_response(db, user.id)


@router.get("/cache/status", response_model=TaskStatusResponse)
def get_cache_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """連携ステータスを返す（軽量ポーリング用）。"""
    cache = GitHubLinkCacheRepository(db).get_by_user(user.id)
    if not cache:
        return TaskStatusResponse(status="completed")
    return TaskStatusResponse(
        status=cache.status,
        error_message=cache.error_message,
        error_code=resolve_async_error_code(cache.error_message),
    )


@router.post("/run", response_model=TaskAcceptedResponse, status_code=202)
@limiter.limit("5/minute")
async def start_github_link(
    request: Request,
    payload: GitHubLinkRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
):
    """GitHub 連携パイプラインをバックグラウンドで開始する。"""
    github_username = user.username

    # 進行中のタスクがあればそのステータスを返す
    cache = get_or_create_github_link_cache(db, user.id)
    service = AsyncTaskCacheService(db, cache)

    # DB 最新状態を取得しつつ pending へアトミック遷移。進行中なら早期リターン
    if not service.try_reset_to_pending():
        return TaskAcceptedResponse(status=cache.status)

    try:
        await service.dispatch(
            background_tasks,
            TaskType.GITHUB_LINK,
            {
                "user_id": user.id,
                "github_username": github_username,
                "github_token": user.github_token,
                "include_forks": payload.include_forks,
            },
            failure_message="タスクの開始に失敗しました",
            logger=logger,
        )
    except Exception:
        _raise_dispatch_failed()

    return TaskAcceptedResponse(status="pending")


@router.post("/run/retry", response_model=TaskAcceptedResponse, status_code=202)
@limiter.limit("5/minute")
async def retry_github_link(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: GitHubLinkRequest | None = None,
    user: User = Depends(require_github_user),
    db: Session = Depends(get_db),
):
    """失敗した GitHub 連携タスクを手動で再実行する。

    ``dead_letter`` 状態のキャッシュのみ再実行可能。
    ``retry_count`` を 0 にリセットし、ステータスを ``pending`` に戻して再ディスパッチする。
    """
    cache = GitHubLinkCacheRepository(db).get_by_user(user.id)
    if not cache:
        raise_app_error(
            status_code=404,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("github_link.no_link_cache"),
            action="先に GitHub 連携を実行してください",
        )
    service = AsyncTaskCacheService(db, cache)
    if not service.is_retryable_terminal():
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("github_link.not_retryable", status=cache.status),
            action="タスクの完了または失敗を待ってから再試行してください",
        )

    github_username = user.username
    include_forks = payload.include_forks if payload else False

    # DB 最新状態を取得しつつアトミック遷移。並列リトライ競合を防ぐ
    if not service.try_reset_to_pending(reset_retry_count=True):
        raise_app_error(
            status_code=409,
            code=ErrorCode.VALIDATION_ERROR,
            message=get_error("github_link.not_retryable", status=cache.status),
            action="タスクの完了または失敗を待ってから再試行してください",
        )

    try:
        await service.dispatch(
            background_tasks,
            TaskType.GITHUB_LINK,
            {
                "user_id": user.id,
                "github_username": github_username,
                "github_token": user.github_token,
                "include_forks": include_forks,
            },
            failure_message="タスクの再実行に失敗しました",
            logger=logger,
        )
    except Exception:
        _raise_dispatch_failed()

    return TaskAcceptedResponse(status="pending")
