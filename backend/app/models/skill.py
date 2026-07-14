"""GitHub 連携スキル推論の 3 層モデル（ADR-0016 D1）。

機械は「幅」（Layer 1-2）、人間は「深さ」（Layer 3）を埋める責務分離。

  - ``github_skills``           : Layer 1 / 正規化エンティティ（language / package）
  - ``github_skill_evidence``   : Layer 2 / 技術×リポの根拠（signal_source・量的シグナル）
  - ``github_skill_proficiency``: Layer 3 / 習熟度・文脈（本フェーズでは未投入）

連携の再実行ごとに Layer 1-2 はユーザー単位で洗い替える（CASCADE で evidence も削除）。
Layer 3 は人間/agent が後追いで埋める想定で、洗い替え時の保全は後続フェーズの課題。
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class GitHubSkill(Base):
    """Layer 1: 正規化されたスキルエンティティ（D1/D2）。

    ``kind`` で language / package を区別する（検出方法と信頼度の出方が異なるため / D2）。
    language の ``ecosystem`` は N/A として空文字で持つ（NULL だと一意制約が効かないため）。
    package ID はエコシステム内で一意 = canonical なので辞書正規化はしない（D3）。
    """

    __tablename__ = "github_skills"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "kind", "ecosystem", "canonical_name",
            name="uq_github_skills_identity",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "language" / "package"
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # 言語=Linguist 正規名 / package=エコシステム内で一意な package ID
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # package のエコシステム（npm/pypi/go/cargo）。language は "" （N/A）
    ecosystem: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )
    # Linguist の group（言語の親）。無ければ NULL
    parent: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    # 表示名・粒度畳みの確定値（agent 提案→人間確定 / D3）。未確定は NULL
    display_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    evidence: Mapped[list["GitHubSkillEvidence"]] = relationship(
        back_populates="skill", cascade="all, delete-orphan"
    )
    proficiency: Mapped["GitHubSkillProficiency | None"] = relationship(
        back_populates="skill", cascade="all, delete-orphan", uselist=False
    )


class GitHubSkillEvidence(Base):
    """Layer 2: 技術×根拠リポの N:N（機械が埋める / D1）。

    ``signal_source`` で根拠の出所を区別する:
      - ``language_bytes``    : Linguist のバイト比率（言語）
      - ``manifest_declared`` : manifest の宣言（package / declare ステージ）
      - ``actual_import``     : import 解析で実使用へ昇格（verify ステージ / 後続）
    """

    __tablename__ = "github_skill_evidence"
    __table_args__ = (
        UniqueConstraint(
            "skill_id", "repo_full_name", "signal_source",
            name="uq_github_skill_evidence_identity",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    skill_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("github_skills.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 根拠リポジトリ（owner/name）と URL（経歴書の証跡用）
    repo_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    signal_source: Mapped[str] = mapped_column(String(30), nullable=False)
    # 0.0–1.0 の信頼度
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 言語シグナル: このリポでのバイト数
    language_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # package シグナル: direct/dev/indirect/peer/build（D7）
    dependency_kind: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None
    )
    # D9(f): manifest の相対パス（package 根拠のみ。例 backend/requirements.txt）
    manifest_path: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    # D9(d): 網羅でない部分スキャン由来か（truncated / cap 打ち切り。証跡の過信防止）
    partial_scan: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    skill: Mapped["GitHubSkill"] = relationship(back_populates="evidence")


class GitHubSkillDisplayDecision(Base):
    """Layer 3: 表示名・粒度畳み込みの人間確定（ADR-0016 D11）。

    agent が提案し人間が確定した「表示名」と「畳み込みグループ」を保持する。
    Layer 1-2（``github_skills`` / ``github_skill_evidence``）は連携再実行のたびに
    ``replace_for_user`` で洗い替え（全削除→再挿入）されるため、確定値をそこに置くと
    再連携で消える。本テーブルは **安定 identity**（``kind`` + ``ecosystem`` +
    ``canonical_name``）をキーに ``github_skills`` から切り離して持ち、洗い替えに耐える。

    ``group_id`` が同じ複数行は 1 スキルへ畳んで表示する（N:1 グルーピング）。
    ``group_id`` が NULL の行は 1:1 の表示名確定（単独スキルのリネーム）。
    ``display_name`` は当該 canonical の確定表示名（グループなら共通のグループ表示名）。
    """

    __tablename__ = "github_skill_display_decisions"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "kind", "ecosystem", "canonical_name",
            name="uq_github_skill_display_decision_identity",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 対象スキルの identity（github_skills の同名カラムと突き合わせる）
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    ecosystem: Mapped[str] = mapped_column(
        String(20), nullable=False, default="", server_default=""
    )
    canonical_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 確定した表示名（グループの場合は共通のグループ表示名）
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # 畳み込みグループ ID。同一 group_id は 1 スキルへ畳む。NULL は 1:1 の単独確定
    group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, default=None)
    # 出所: "agent"（提案そのまま採用）/ "human"（人間が編集）
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="human")
    # 人間レビュー済みか（確定フローを通ったら True）
    reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class GitHubSkillProficiency(Base):
    """Layer 3: 習熟度・文脈（人間/agent が後追いで埋める / D1）。

    本フェーズ（基盤＋declare）では投入しない。スキーマだけ用意する。
    """

    __tablename__ = "github_skill_proficiency"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    skill_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("github_skills.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # 自己評価レベル（例: beginner/intermediate/advanced）。確定まで NULL
    self_assessed_level: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None
    )
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    scale: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    # 出所: "agent"（生成）/ "human"（手入力）
    source: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    # 人間レビュー済みか
    reviewed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    skill: Mapped["GitHubSkill"] = relationship(back_populates="proficiency")
