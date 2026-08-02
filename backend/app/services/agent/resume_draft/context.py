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
    DEPENDENCY_KIND_DIRECT,
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
_PACKAGE_SIGNAL_ACTUAL_IMPORT = "actual_import"

# ADR-0026 決定 4 で追加した選定シグナル。スキーマ上は既定値を持つ Optional なので
# パースは通ってしまうが、シグナル欠落のまま選定すると品質を担保できない。生 JSON の
# キー有無で旧形式を判別し、"repos" 欠落と同じ 409 導線へ倒す。
# 代表キー 1 つでは「一部だけ持つキャッシュ」を見逃すため、全キーの存在を要求する。
_SELECTION_SIGNAL_KEYS = frozenset(
    {
        "topics",
        "language_bytes_total",
        "direct_dependency_count",
        "ecosystem_count",
        "has_infra",
    }
)


class ResumeDraftSourceUnavailableError(Exception):
    """ドラフト生成に必要な連携データが無い（未連携・旧形式キャッシュ・進行中）。

    router で 409 にマッピングし、GitHub 連携の（再）実行を促す。
    """


class ResumeDraftNoRepositoriesError(ResumeDraftSourceUnavailableError):
    """連携は完了しているが分析対象リポジトリが 0 件（再連携では回復しない）。

    旧形式キャッシュ（再連携で回復する）とは区別し、router で「公開リポジトリを追加して
    再連携」という別の導線を案内する。``ResumeDraftSourceUnavailableError`` のサブクラス
    なので、router では本クラスを先に catch すること。
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
    # ADR-0018 より前の旧形式は result に "repos" キー自体が無い（再連携で回復する）。
    # 一方 ADR-0018 以降は分析対象が 0 件でも "repos": [] が保存されるため、生 JSON の
    # キー有無で両者を区別する（Pydantic 検証後は default_factory=[] のため区別できない）。
    if "repos" not in cache.result:
        raise ResumeDraftSourceUnavailableError(
            "連携キャッシュにリポジトリサマリがありません（旧形式）"
        )
    # ADR-0026 決定 4 より前のキャッシュは選定シグナルを持たない。Pydantic は既定値で
    # 通してしまうため、ここも生 JSON のキー有無で判別して再連携を促す。
    if any(
        isinstance(raw, dict) and not _SELECTION_SIGNAL_KEYS.issubset(raw)
        for raw in cache.result["repos"] or []
    ):
        raise ResumeDraftSourceUnavailableError(
            "連携キャッシュに選定シグナルがありません（旧形式）"
        )
    try:
        result = GitHubLinkResponse.model_validate(cache.result)
    except ValidationError:
        # キャッシュ JSON がスキーマに合わない場合も再連携で回復できるため 409 側に倒す
        logger.warning("連携キャッシュの検証に失敗（再連携が必要）", exc_info=True)
        raise ResumeDraftSourceUnavailableError("連携キャッシュを解釈できません") from None
    if not result.repos:
        # 新形式だが分析対象リポジトリが 0 件。再連携では回復しないため別導線を案内する
        raise ResumeDraftNoRepositoriesError("分析対象のリポジトリがありません")

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
                evidence.dependency_kind == DEPENDENCY_KIND_DIRECT
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
