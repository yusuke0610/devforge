"""GitHub 連携タスクの実行サービス。

進捗通知付きでパイプラインを駆動し、結果を ``GitHubLinkCache`` に保存する。

worker は本サービスを呼ぶだけで、状態遷移・進捗などは本モジュールに集約する。

libSQL (Hrana over HTTP) の idle stream timeout を避けるため、GitHub API 収集の
前後でセッションを開閉する。
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...core.encryption import decrypt_field
from ...core.logging_utils import get_logger
from ...core.messages import get_error
from ...models import GitHubLinkCache
from ...repositories.github_link import GitHubLinkCacheRepository
from ...repositories.skill import GitHubSkillRepository
from ..progress_service import set_progress
from ..tasks.exceptions import NonRetryableError
from ..tasks.handlers.base import SessionFactory
from .github.contributions import fetch_all_contribution_calendars
from .github_collector import GitHubUserNotFoundError, collect_repos
from .pipeline import aggregate_intelligence
from .response_mapper import map_pipeline_result
from .skills import RepoSkillInput, aggregate_skills

logger = get_logger(__name__)

_TOTAL_STEPS = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_github_link_cache(db: Session, user_id: str) -> GitHubLinkCache:
    """ユーザーの GitHubLinkCache レコードを取得し、存在しなければ作成する。

    取得・作成ロジックは GitHubLinkCacheRepository に集約済み。本関数は既存呼び出し元
    （router）の入口を維持するための薄いラッパ。
    """
    return GitHubLinkCacheRepository(db).get_or_create(user_id)


async def run_github_link(session_factory: SessionFactory, payload: dict) -> None:
    """GitHub 連携パイプラインを実行し、結果をキャッシュに保存する。

    フェーズ構成:
      - A: payload 検証 + processing マーク（短命セッション）
      - B: GitHub API 取得 + スキル集計（DB セッション無し）
      - C: 結果書き戻し（新セッション）
    """
    user_id = payload.get("user_id")
    # 必須キー欠落・キャッシュ不在はいずれもディスパッチ側のバグであり、
    # リトライしても回復しないため NonRetryableError で worker に dead_letter を委ねる。
    if not user_id:
        message = "GitHub 連携タスクのペイロードに user_id がありません"
        logger.error(message, extra={"payload_keys": list(payload.keys())})
        raise NonRetryableError(f"{message} (payload_keys={list(payload.keys())})")
    task_id = user_id

    # ── フェーズA: 検証 + processing マーク ─────────────────────────────────
    with session_factory() as db:
        cache = GitHubLinkCacheRepository(db).get_by_user(user_id)
        if not cache:
            message = "GitHub 連携キャッシュが見つかりません"
            logger.error(message, extra={"user_id": user_id})
            raise NonRetryableError(f"{message} (user_id={user_id})")

        cache.status = "processing"
        cache.started_at = _now()
        # 前回実行の警告が残らないようリセット（error_message はディスパッチ時点でリセット済み）
        cache.warning_message = None
        db.commit()

    # ── フェーズB: GitHub 取得 + 集計（DB セッション無し）──────────────────
    token = decrypt_field(payload["github_token"]) if payload.get("github_token") else None

    try:
        # ステップ 1: リポジトリ一覧取得
        await set_progress(task_id, 1, _TOTAL_STEPS, "リポジトリ一覧取得中...")

        async def _on_repo_fetched(done: int, total: int) -> None:
            await set_progress(
                task_id,
                2,
                _TOTAL_STEPS,
                "リポジトリ詳細取得中...",
                sub_progress={"done": done, "total": total},
            )

        repos = await collect_repos(
            username=payload["github_username"],
            token=token,
            include_forks=payload.get("include_forks", False),
            on_repo_fetched=_on_repo_fetched,
            collect_manifests=True,
        )
    except GitHubUserNotFoundError as exc:
        with session_factory() as db:
            cache = GitHubLinkCacheRepository(db).get_by_user(user_id)
            if cache:
                cache.status = "dead_letter"
                cache.error_message = (
                    f"GitHubユーザーが見つかりません: {payload['github_username']}"
                )
                cache.completed_at = _now()
                db.commit()
        raise exc

    # コントリビューションカレンダー取得（補助処理: 失敗しても連携は継続）
    calendars: list = []
    contribution_fetch_failed = False
    if token:
        ok, calendars = await fetch_all_contribution_calendars(
            payload["github_username"], token
        )
        # 取得失敗のときだけ警告対象にする（貢献年が無いだけなら警告しない）
        contribution_fetch_failed = not ok

    # ステップ 3: スキル集計
    await set_progress(task_id, 3, _TOTAL_STEPS, "スキル集計中...")

    # 3 層スキル（ADR-0016 / discover + declare）の中間表現を組み立てる（I/O 無し）。
    detected_skills = aggregate_skills(
        [
            RepoSkillInput(
                full_name=f"{repo.owner}/{repo.name}",
                url=f"https://github.com/{repo.owner}/{repo.name}",
                languages=repo.languages,
                package_declarations=repo.package_declarations,
                manifest_scan_partial=repo.manifest_scan_partial,
            )
            for repo in repos
        ]
    )

    # dashboard 表示用サマリ（件数・言語バイト数）を検出スキルから組む。
    result = aggregate_intelligence(payload["github_username"], repos, detected_skills)

    response = map_pipeline_result(result)
    response.contribution_calendars = calendars
    result_dict = response.model_dump()

    # ── フェーズC: 結果書き戻し（新セッション）─────────────────────────────
    # ステップ 4: DB 保存
    await set_progress(task_id, 4, _TOTAL_STEPS, "結果を保存中...")
    with session_factory() as db:
        cache = GitHubLinkCacheRepository(db).get_by_user(user_id)
        if not cache:
            logger.warning(
                "結果書き戻し時にキャッシュが見つかりません",
                extra={"user_id": user_id},
            )
            return
        # 先に 3 層スキルを洗い替えで永続化する（ADR-0016）。
        # ここで失敗した場合は status を completed にしないことで、
        # 「completed なのにスキルが無い」状態を避ける（retry で再永続化される）。
        GitHubSkillRepository(db, user_id).replace_for_user(detected_skills)

        cache.result = result_dict
        cache.status = "completed"
        cache.error_message = None
        # コントリビューション取得失敗は連携自体を失敗させず警告として残す
        # （token が無い場合は取得を試行していないため警告は出さない。
        #   貢献年がゼロで calendars が空でも、取得自体が成功なら警告しない）
        cache.warning_message = (
            get_error("github_link.contribution_fetch_failed")
            if contribution_fetch_failed
            else None
        )
        cache.completed_at = _now()
        db.commit()

    # ステップ 5: 完了
    await set_progress(task_id, 5, _TOTAL_STEPS, "完了")
