"""GitHub 連携スキル（3 層）のデータアクセス（ADR-0016）。

連携の実行ごとに Layer 1-2 をユーザー単位で洗い替える。Layer 3（proficiency）は
本フェーズでは投入しないが、CASCADE 削除の対象になる点に留意（保全は後続課題）。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import GitHubSkill, GitHubSkillEvidence
from ..services.intelligence.skills import DetectedSkill


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
