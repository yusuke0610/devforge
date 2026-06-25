"""GitHub 連携スキル推論（3 層）の API スキーマ（ADR-0016）。"""

from typing import List, Optional

from pydantic import BaseModel, Field


class SkillEvidence(BaseModel):
    """Layer 2: 技術×リポの根拠。"""

    repo_full_name: str = Field(description="根拠リポジトリ（owner/name）")
    repo_url: str = Field(description="リポジトリ URL（経歴書の証跡用）")
    signal_source: str = Field(
        description="根拠の出所（language_bytes / manifest_declared / actual_import）"
    )
    confidence: float = Field(description="信頼度（0.0–1.0）")
    language_bytes: Optional[int] = Field(
        default=None, description="言語シグナルのバイト数（package では null）"
    )
    dependency_kind: Optional[str] = Field(
        default=None,
        description="依存の種類（direct/dev/indirect/peer/build。言語では null）",
    )


class SkillProficiency(BaseModel):
    """Layer 3: 習熟度・文脈（人間/agent が後追いで埋める。本フェーズは未投入）。"""

    self_assessed_level: Optional[str] = Field(default=None, description="自己評価レベル")
    narrative: Optional[str] = Field(default=None, description="文脈の説明文")
    duration_months: Optional[int] = Field(default=None, description="従事期間（月）")
    scale: Optional[str] = Field(default=None, description="規模")
    source: Optional[str] = Field(default=None, description="出所（agent / human）")
    reviewed: bool = Field(default=False, description="人間レビュー済みか")


class GitHubSkillItem(BaseModel):
    """Layer 1: 正規化スキルと、その根拠・習熟度。"""

    kind: str = Field(description="スキル種別（language / package）")
    canonical_name: str = Field(description="正規名（言語=Linguist 名 / package=package ID）")
    ecosystem: Optional[str] = Field(
        default=None, description="package のエコシステム（npm/pypi/go/cargo）。言語では null"
    )
    parent: Optional[str] = Field(default=None, description="親（Linguist の group）")
    display_name: Optional[str] = Field(
        default=None, description="表示名（粒度畳みの確定値。未確定は null）"
    )
    evidence: List[SkillEvidence] = Field(default_factory=list)
    proficiency: Optional[SkillProficiency] = Field(default=None)


class GitHubSkillsResponse(BaseModel):
    """ユーザーの GitHub 連携スキル一覧（3 層）。"""

    skills: List[GitHubSkillItem] = Field(default_factory=list)
