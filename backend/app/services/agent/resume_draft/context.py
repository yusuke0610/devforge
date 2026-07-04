"""経歴書ドラフト生成の入力データ取得（DB 読み取り専用 / ADR-0018）。

DB アクセスは本モジュールに閉じ込める（mapper / draft_service は DB に触れない。
チャットの context_builder と同じ責務分担）。SELECT のみで commit / flush / add は行わない。

連携キャッシュの ``result.repos``（連携実行時のリポジトリサマリ）と、スキル証跡
``github_skill_evidence``（ADR-0016 / スキル → リポの N:N）を「リポジトリ → 技術」に
反転した辞書を ``DraftSource`` に束ねて返す。両者は同一連携実行時点のスナップショット
なのでリポジトリ集合が一致する前提を置ける。
"""

import logging
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy.orm import Session

from ....models import User
from ....repositories.github_link import GitHubLinkCacheRepository
from ....repositories.skill import GitHubSkillRepository
from ....schemas.github_link import AnalyzedRepoSummary, GitHubLinkResponse
from ...intelligence.skills.types import (
    SKILL_KIND_INFRA,
    SKILL_KIND_LANGUAGE,
    SKILL_KIND_PACKAGE,
)

logger = logging.getLogger(__name__)

# スキル種別 → 経歴書の技術スタックカテゴリ（schemas/resume.py の Literal に収まる値のみ）
_KIND_TO_CATEGORY: dict[str, str] = {
    SKILL_KIND_LANGUAGE: "language",
    SKILL_KIND_PACKAGE: "framework",
    SKILL_KIND_INFRA: "iac",
}

# package スキルを技術スタックに採用する根拠の下限。manifest の間接依存
# （dependency_kind が direct 以外かつ実 import 未確認）は「使った技術」とは
# 言えないため経歴書には載せない
_PACKAGE_DEPENDENCY_KIND_DIRECT = "direct"
_PACKAGE_SIGNAL_ACTUAL_IMPORT = "actual_import"


class ResumeDraftSourceUnavailableError(Exception):
    """ドラフト生成に必要な連携データが無い（未連携・旧形式キャッシュ・進行中）。

    router で 409 にマッピングし、GitHub 連携の（再）実行を促す。
    """


@dataclass(frozen=True)
class RepoTechnology:
    """リポジトリ 1 件に紐づく技術 1 件（スキル証跡の反転結果）。"""

    category: str
    name: str
    confidence: float
    # 言語スキルのみ持つ、このリポでのバイト数（リポ選定のタイブレークに使う）
    language_bytes: int = 0


@dataclass(frozen=True)
class DraftSource:
    """ドラフト生成のルールベースマッピング（mapper）への入力一式。"""

    username: str
    email: str
    repos: list[AnalyzedRepoSummary] = field(default_factory=list)
    # repo_full_name → 技術リスト（証跡の反転。順序は保証しない。並べ替えは mapper が担う）
    repo_technologies: dict[str, list[RepoTechnology]] = field(default_factory=dict)


def build_draft_source(db: Session, user: User) -> DraftSource:
    """連携キャッシュとスキル証跡からドラフト生成の入力を組み立てる。

    Raises:
        ResumeDraftSourceUnavailableError: 連携が未完了、またはキャッシュが
            リポジトリサマリを持たない旧形式（ADR-0018 以前の連携結果）。
    """
    cache = GitHubLinkCacheRepository(db).get_by_user(user.id)
    if not cache or cache.status != "completed" or not cache.result:
        raise ResumeDraftSourceUnavailableError(
            f"GitHub 連携が完了していません (status={cache.status if cache else None})"
        )
    try:
        result = GitHubLinkResponse.model_validate(cache.result)
    except ValidationError:
        # キャッシュ JSON がスキーマに合わない場合も再連携で回復できるため 409 側に倒す
        logger.warning("連携キャッシュの検証に失敗（再連携が必要）", exc_info=True)
        raise ResumeDraftSourceUnavailableError("連携キャッシュを解釈できません") from None
    if not result.repos:
        # ADR-0018 より前に保存された旧形式。再連携でサマリが埋まる
        raise ResumeDraftSourceUnavailableError(
            "連携キャッシュにリポジトリサマリがありません（旧形式）"
        )

    return DraftSource(
        username=user.username,
        email=user.email or "",
        repos=list(result.repos),
        repo_technologies=_invert_skill_evidence(db, user.id),
    )


def _invert_skill_evidence(db: Session, user_id: str) -> dict[str, list[RepoTechnology]]:
    """スキル証跡（スキル → リポ）を「リポ → 技術」に反転する。

    - language: 常に採用（language_bytes を保持）
    - package: direct 宣言または実 import 確認済みのみ採用
    - infra: 常に採用
    同一（リポ・カテゴリ・技術名）が複数証跡（manifest_declared と actual_import 等）で
    現れた場合は confidence / language_bytes の大きい方に畳む。
    """
    merged: dict[str, dict[tuple[str, str], RepoTechnology]] = {}
    for skill in GitHubSkillRepository(db, user_id).list_for_user():
        category = _KIND_TO_CATEGORY.get(skill.kind)
        if category is None:
            logger.warning("未知のスキル種別を技術スタックから除外: kind=%s", skill.kind)
            continue
        name = skill.display_name or skill.canonical_name
        for evidence in skill.evidence:
            if skill.kind == SKILL_KIND_PACKAGE and not (
                evidence.dependency_kind == _PACKAGE_DEPENDENCY_KIND_DIRECT
                or evidence.signal_source == _PACKAGE_SIGNAL_ACTUAL_IMPORT
            ):
                continue
            per_repo = merged.setdefault(evidence.repo_full_name, {})
            key = (category, name)
            candidate = RepoTechnology(
                category=category,
                name=name,
                confidence=evidence.confidence or 0.0,
                language_bytes=evidence.language_bytes or 0,
            )
            existing = per_repo.get(key)
            if existing is None:
                per_repo[key] = candidate
            else:
                per_repo[key] = RepoTechnology(
                    category=category,
                    name=name,
                    confidence=max(existing.confidence, candidate.confidence),
                    language_bytes=max(existing.language_bytes, candidate.language_bytes),
                )
    return {repo: list(entries.values()) for repo, entries in merged.items()}
