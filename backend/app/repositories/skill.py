"""GitHub 連携スキル（3 層）のデータアクセス（ADR-0016）。

連携の実行ごとに Layer 1-2 をユーザー単位で洗い替える。Layer 3（proficiency）は
本フェーズでは投入しないが、CASCADE 削除の対象になる点に留意（保全は後続課題）。
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import GitHubSkill, GitHubSkillDisplayDecision, GitHubSkillEvidence
from ..services.intelligence.skills import DetectedSkill


@dataclass(frozen=True)
class DisplayDecisionInput:
    """1 スキルの表示名確定入力（identity + 確定表示名 + グループ / ADR-0016 D11）。

    ``group_id`` が同じ複数入力は 1 スキルへ畳む（N:1）。NULL は 1:1 の単独確定。
    """

    kind: str
    ecosystem: str
    canonical_name: str
    display_name: str
    group_id: str | None = None
    source: str = "human"


class GitHubSkillRepository:
    """ユーザーの GitHub 連携スキルの読み書き。"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def list_for_user(self) -> list[GitHubSkill]:
        """ユーザーのスキルを evidence/proficiency 付きで取得する。"""
        statement = (
            select(GitHubSkill)
            .where(GitHubSkill.user_id == self.user_id)
            .options(
                selectinload(GitHubSkill.evidence),
                selectinload(GitHubSkill.proficiency),
            )
            .order_by(GitHubSkill.kind, GitHubSkill.canonical_name)
        )
        return list(self.db.scalars(statement).all())

    def replace_for_user(self, detected: list[DetectedSkill]) -> None:
        """ユーザーの Layer 1-2 を洗い替える（既存削除 → 一括挿入）。

        既存行は ORM セッション経由で削除し、``cascade="all, delete-orphan"`` で
        evidence/proficiency も確実に消す。Core 一括 DELETE は DB の
        ``ON DELETE CASCADE`` に依存するが、SQLite/libSQL は ``PRAGMA foreign_keys``
        が ON でないと FK を強制せず孤児行が残るため、バックエンド非依存の ORM 削除にする。
        """
        existing = self.db.scalars(
            select(GitHubSkill).where(GitHubSkill.user_id == self.user_id)
        ).all()
        for skill in existing:
            self.db.delete(skill)
        # 同一 identity（user_id+kind+ecosystem+canonical_name）の再挿入前に削除を確定する
        self.db.flush()

        for item in detected:
            skill = GitHubSkill(
                user_id=self.user_id,
                kind=item.kind,
                canonical_name=item.canonical_name,
                ecosystem=item.ecosystem,
                parent=item.parent,
                display_name=item.display_name,
            )
            skill.evidence = [
                GitHubSkillEvidence(
                    repo_full_name=ev.repo_full_name,
                    repo_url=ev.repo_url,
                    signal_source=ev.signal_source,
                    confidence=ev.confidence,
                    language_bytes=ev.language_bytes,
                    dependency_kind=ev.dependency_kind,
                    manifest_path=ev.manifest_path,
                    partial_scan=ev.partial_scan,
                )
                for ev in item.evidence
            ]
            self.db.add(skill)

        self.db.commit()


class GitHubSkillDisplayDecisionRepository:
    """スキル表示名の human-in-the-loop 確定（Layer 3）の読み書き（ADR-0016 D11）。

    ``github_skills`` とは独立し、安定 identity（kind + ecosystem + canonical_name）を
    キーに確定表示名・畳み込みグループを持つ。連携再実行の洗い替え（``replace_for_user``）
    の影響を受けないため、一度確定した表示名は再連携後も残る。
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get_for_user(self) -> list[GitHubSkillDisplayDecision]:
        """ユーザーの確定済み表示名を全件取得する。"""
        statement = select(GitHubSkillDisplayDecision).where(
            GitHubSkillDisplayDecision.user_id == self.user_id
        )
        return list(self.db.scalars(statement).all())

    def upsert_many(self, decisions: list[DisplayDecisionInput]) -> None:
        """確定表示名を identity 単位で upsert する（既存は上書き、無ければ挿入）。

        同一 identity（kind + ecosystem + canonical_name）が既にあれば表示名・グループ・
        出所を更新し、無ければ新規挿入する。バッチ確定（web のレビュー→確定）で使う。
        """
        existing = {
            (d.kind, d.ecosystem, d.canonical_name): d for d in self.get_for_user()
        }
        for item in decisions:
            key = (item.kind, item.ecosystem, item.canonical_name)
            current = existing.get(key)
            if current is not None:
                current.display_name = item.display_name
                current.group_id = item.group_id
                current.source = item.source
                current.reviewed = True
            else:
                self.db.add(
                    GitHubSkillDisplayDecision(
                        user_id=self.user_id,
                        kind=item.kind,
                        ecosystem=item.ecosystem,
                        canonical_name=item.canonical_name,
                        display_name=item.display_name,
                        group_id=item.group_id,
                        source=item.source,
                        reviewed=True,
                    )
                )
        self.db.commit()

    def delete_by_identities(
        self, identities: list[tuple[str, str, str]]
    ) -> int:
        """指定 identity（kind + ecosystem + canonical_name）の確定行を削除する（#496）。

        ユーザー自身の確定行だけを対象にし（``user_id`` 固定）、機械デフォルトへ戻す。
        存在しない identity はスキップ（冪等）。削除件数を返す。畳み込みグループを解く場合は
        当該グループの全メンバー identity をまとめて渡す。
        """
        identity_set = set(identities)
        if not identity_set:
            return 0
        deleted = 0
        for decision in self.get_for_user():
            key = (decision.kind, decision.ecosystem, decision.canonical_name)
            if key in identity_set:
                self.db.delete(decision)
                deleted += 1
        self.db.commit()
        return deleted
