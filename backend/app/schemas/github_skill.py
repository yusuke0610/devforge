"""GitHub 連携スキル推論（3 層）の API スキーマ（ADR-0016）。"""

from typing import List, Optional

from pydantic import BaseModel, Field

from .agent import AgentModelAlias


class SkillEvidence(BaseModel):
    """Layer 2: 技術×リポの根拠。"""

    repo_full_name: str = Field(description="根拠リポジトリ（owner/name）")
    repo_url: str = Field(description="リポジトリ URL（経歴書の証跡用）")
    signal_source: str = Field(
        description=(
            "根拠の出所（language_bytes / manifest_declared / actual_import / infra_declared）"
        )
    )
    confidence: float = Field(description="信頼度（0.0–1.0）")
    language_bytes: Optional[int] = Field(
        default=None, description="言語シグナルのバイト数（package では null）"
    )
    dependency_kind: Optional[str] = Field(
        default=None,
        description="依存の種類（direct/dev/indirect/peer/build。言語では null）",
    )
    manifest_path: Optional[str] = Field(
        default=None,
        description=(
            "根拠ファイルの相対パス（package の manifest / infra の .tf。"
            "例 backend/requirements.txt・infra/main.tf。言語では null）"
        ),
    )
    partial_scan: bool = Field(
        default=False,
        description="網羅でない部分スキャン由来か（証跡の過信防止。言語では常に false）",
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

    kind: str = Field(description="スキル種別（language / package / infra）")
    canonical_name: str = Field(
        description=(
            "正規名（言語=Linguist 名 / package=package ID / "
            "infra=provider 名または raw resource type）"
        )
    )
    ecosystem: Optional[str] = Field(
        default=None,
        description=(
            "エコシステム（package は npm/pypi/go/cargo、infra は terraform 等）。言語では null"
        ),
    )
    parent: Optional[str] = Field(default=None, description="親（Linguist の group）")
    display_name: Optional[str] = Field(
        default=None, description="機械（Linguist）由来の表示補正。未補正は null"
    )
    # D11: human-in-the-loop の確定表示名・畳み込みグループ（github_skill_display_decisions 由来）
    confirmed_display_name: Optional[str] = Field(
        default=None, description="人間が確定した表示名（未確定は null / D11）"
    )
    group_id: Optional[str] = Field(
        default=None,
        description="畳み込みグループ ID。同一 group_id のスキルは 1 表示へ畳む（D11）",
    )
    decision_source: Optional[str] = Field(
        default=None, description="確定の出所（agent / human。未確定は null / D11）"
    )
    decision_reviewed: bool = Field(
        default=False, description="人間レビュー済みか（D11）"
    )
    evidence: List[SkillEvidence] = Field(default_factory=list)
    proficiency: Optional[SkillProficiency] = Field(default=None)


class GitHubSkillsResponse(BaseModel):
    """ユーザーの GitHub 連携スキル一覧（3 層）。"""

    skills: List[GitHubSkillItem] = Field(default_factory=list)


class SkillDisplayProposeRequest(BaseModel):
    """表示名提案（agent）のリクエスト（ADR-0016 D11）。

    提案対象スキルはサーバーが連携結果から決めるため、クライアントは使用モデルのみ指定する。
    """

    # 使用モデル。既定は haiku（ADR-0023 で課金撤去済み・全モデル無料）
    model: AgentModelAlias = "haiku"


class SkillIdentityRef(BaseModel):
    """スキルの安定 identity（github_skills と一致 / D11）。"""

    kind: str = Field(description="スキル種別（language / package / infra）")
    ecosystem: str = Field(default="", description="エコシステム（language は空文字）")
    canonical_name: str = Field(description="正規名（package ID / 言語名 / raw resource type）")


class SkillDisplayProposedGroup(BaseModel):
    """agent が提案した 1 表示スキル（表示名 + 畳むメンバー群 / D11）。"""

    display_name: str = Field(description="提案する表示名")
    members: List[SkillIdentityRef] = Field(
        default_factory=list, description="このグループに畳むスキルの identity"
    )


class SkillDisplayProposeResponse(BaseModel):
    """表示名提案の結果（永続化されない。人間がレビュー・確定する / D11）。"""

    groups: List[SkillDisplayProposedGroup] = Field(default_factory=list)


class SkillDisplayDecisionInput(BaseModel):
    """人間が確定する 1 スキルの表示名（identity + 確定表示名 + グループ / D11）。"""

    kind: str = Field(description="スキル種別")
    ecosystem: str = Field(default="", description="エコシステム（language は空文字）")
    canonical_name: str = Field(description="正規名")
    display_name: str = Field(min_length=1, max_length=255, description="確定した表示名")
    group_id: Optional[str] = Field(
        default=None, description="畳み込みグループ ID（単独確定は null）"
    )
    source: str = Field(default="human", description="出所（agent / human）")


class SkillDisplayConfirmRequest(BaseModel):
    """表示名確定（人間）のバッチリクエスト（ADR-0016 D11）。"""

    decisions: List[SkillDisplayDecisionInput] = Field(default_factory=list)


class SkillDisplayResetRequest(BaseModel):
    """表示名確定の解除（リセット）リクエスト（ADR-0016 D11 / #496）。

    指定 identity の確定行（Layer 3）を削除し、機械デフォルト（機械 display_name /
    canonical）へ完全に戻す。同一グループの全メンバー identity を渡せば畳み込みも解ける。
    """

    identities: List[SkillIdentityRef] = Field(default_factory=list)
