"""職務経歴書（Resume）の Pydantic スキーマ。

FE 同期: 本モジュールの各 Item / レスポンス型は ``frontend/src/types.ts`` の Career 系 type
（``ResumeQualification`` / ``CareerTechnologyStack`` / ``TeamMember`` / ``ProjectTeam`` /
``CareerProject`` / ``CareerClient`` / ``CareerExperience`` 等）と対になる DTO。
言語境界のため codegen 未導入の手動同期で運用している（エラーコードの errors.py と同方針）。
フィールドを増減・rename する場合は対応する FE type も同時に更新すること。

非IT経歴: ``Experience.is_it_company=False`` のとき取引先/プロジェクトを持たず
``Experience.description``（詳細）のみ使う。
休暇: ``Client.is_vacation=True`` のとき取引先ではなく在籍中の休暇を表し、
``Client.vacation_*``（期間・詳細）を使う。
"""

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from ..core.date_utils import to_jst
from ..core.messages import get_error


class ResumeQualificationItem(BaseModel):
    # 取得年月・名称ともに必須（保存時にフロント payloadBuilders も必須を強制する）。
    # PDF インポートで日付が無い場合はプレビュー用 ImportQualificationItem が許容し、
    # 保存前にユーザーがフォームで日付を補完する運用とする。
    acquired_date: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(from_attributes=True)


class TechnologyStackItem(BaseModel):
    category: Literal[
        "language",
        "framework",
        "os",
        "db",
        "cloud_provider",
        "container",
        "iac",
        "vcs",
        "ci_cd",
        "project_tool",
        "monitoring",
        "middleware",
        "ai_agent",
    ]
    name: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(from_attributes=True)


class TeamMember(BaseModel):
    """体制の役割ごとの人数。"""

    role: str = Field(max_length=60)
    count: int = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class ProjectTeam(BaseModel):
    """プロジェクト体制（全体人数 + 役割別内訳）。"""

    total: str = Field(max_length=60, default="")
    members: list[TeamMember] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ProjectPeriod(BaseModel):
    """プロジェクトの在籍期間（1 案件に複数持てる）。"""

    start_date: str = Field(max_length=30, default="")
    # 参画中（is_current=True）の場合は "" を渡す契約。
    end_date: str = Field(default="", max_length=30)
    is_current: bool = False

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_dates(self) -> "ProjectPeriod":
        if not self.start_date.strip():
            raise ValueError(get_error("validation.start_date_required"))
        if self.is_current:
            self.end_date = ""
            return self
        if not self.end_date.strip():
            raise ValueError(get_error("validation.end_date_required"))
        if self.end_date < self.start_date:
            raise ValueError(get_error("validation.date_range_invalid"))
        return self


class Project(BaseModel):
    name: str = Field(max_length=200, default="")
    periods: list[ProjectPeriod] = Field(default_factory=list)
    role: str = Field(max_length=200, default="")
    # 課題・行動・成果を統合した自由記述欄（見出し「詳細」）
    description: str = Field(max_length=4500, default="")
    team: ProjectTeam = Field(default_factory=ProjectTeam)
    technology_stacks: list[TechnologyStackItem] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_fields(cls, data: dict) -> dict:
        """旧形式の後方互換処理。
        - scale → team
        - start_date/end_date/is_current（フラット）→ periods[0]
        """
        if not isinstance(data, dict):
            return data
        if "scale" in data and "team" not in data:
            scale = data.pop("scale")
            data["team"] = {"total": str(scale) if scale else "", "members": []}
        if "start_date" in data and "periods" not in data:
            data["periods"] = [
                {
                    "start_date": data.pop("start_date", ""),
                    "end_date": data.pop("end_date", ""),
                    "is_current": data.pop("is_current", False),
                }
            ]
        return data

class Client(BaseModel):
    """ユーザ（常駐先/クライアント企業）。

    ``is_vacation=True`` の場合は取引先ではなく在籍中の休暇（育児/介護/留学等）を表し、
    name / projects の代わりに ``vacation_*`` 期間と詳細を保持する。
    """

    name: str = Field(max_length=200, default="")
    has_client: bool = True
    projects: list[Project] = Field(default_factory=list)
    # 休暇エントリ。True のとき vacation_* を期間・詳細として扱い projects は無視する。
    is_vacation: bool = False
    vacation_start_date: str = Field(default="", max_length=30)
    # 継続中（vacation_is_current=True）の場合は "" を渡す契約。
    vacation_end_date: str = Field(default="", max_length=30)
    vacation_is_current: bool = False
    vacation_description: str = Field(max_length=4500, default="")

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def validate_vacation_dates(self) -> "Client":
        """休暇の期間を検証する（Experience.validate_dates と同じ契約）。

        休暇でない取引先は検証対象外。開始年月は必須、継続中なら end を ""
        に正規化し、それ以外は終了年月必須かつ end >= start を要求する。
        """
        if not self.is_vacation:
            return self
        if not self.vacation_start_date.strip():
            raise ValueError(get_error("validation.start_date_required"))
        if self.vacation_is_current:
            self.vacation_end_date = ""
            return self
        if not self.vacation_end_date.strip():
            raise ValueError(get_error("validation.end_date_required"))
        if self.vacation_end_date < self.vacation_start_date:
            raise ValueError(get_error("validation.date_range_invalid"))
        return self


class Experience(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    business_description: str = Field(min_length=1, max_length=200)
    # 在籍開始年月は必須だが、空欄時に日本語メッセージを返すため min_length ではなく
    # validate_dates で検証する（English な Pydantic 既定メッセージを避ける）。
    # 従業員数・資本金は会社名があっても任意入力のまま（required にしない）。
    start_date: str = Field(default="", max_length=30)
    end_date: str = Field(default="", max_length=30)
    is_current: bool = False
    employee_count: str = Field(max_length=60, default="")
    capital: str = Field(max_length=120, default="")
    # 資本金の単位。既定は後方互換のため「千万円」。FE の CapitalUnit と対の DTO。
    capital_unit: Literal["万円", "百万円", "千万円", "億円"] = Field(default="千万円")
    # IT 企業かどうか。False（非IT）の場合は取引先/プロジェクトを持たず description を使う。
    is_it_company: bool = True
    # 非IT企業の職務内容を記述する自由記述欄（見出し「詳細」）。business_description=事業内容 とは別。
    description: str = Field(max_length=4500, default="")
    clients: list[Client] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _migrate_projects_to_clients(cls, data: dict) -> dict:
        """旧形式（projects直下）を clients にラップする後方互換処理。"""
        if isinstance(data, dict) and "projects" in data and "clients" not in data:
            projects = data.pop("projects")
            data["clients"] = [{"name": "", "projects": projects}]
        return data

    @model_validator(mode="after")
    def validate_dates(self) -> "Experience":
        """在籍開始年月の必須チェック、終了年月の必須チェック、日付範囲の検証を行う。

        開始年月が空のまま repositories 層に渡ると ``parse_year_month("")`` が
        ValueError を投げて 500 になる。手前で 422（日本語メッセージ）として返す。
        """
        if not self.start_date.strip():
            raise ValueError(get_error("validation.start_date_required"))
        if self.is_current:
            self.end_date = ""
            return self
        if not self.end_date.strip():
            raise ValueError(get_error("validation.end_date_required"))
        if self.end_date < self.start_date:
            raise ValueError(get_error("validation.date_range_invalid"))
        return self


# 簡易メール形式（RFC 5322 完全準拠ではなく UX 優先の最小チェック）。FE 側 payloadBuilders と一致させる。
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# GitHub アカウント URL の接頭辞。値があるときのみ前方一致で検証する。
_GITHUB_URL_PREFIX = "https://github.com/"


class ResumeBase(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=1, max_length=255)
    github_url: str = Field(default="", max_length=255)
    career_summary: str = Field(min_length=1, max_length=2000)
    self_pr: str = Field(min_length=1, max_length=2000)
    experiences: list[Experience] = Field(default_factory=list)
    qualifications: list[ResumeQualificationItem] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """メールアドレスの簡易形式チェック。不正なら 422（日本語メッセージ）で返す。"""
        if not _EMAIL_PATTERN.match(value.strip()):
            raise ValueError(get_error("validation.email_invalid"))
        return value

    @field_validator("github_url")
    @classmethod
    def validate_github_url(cls, value: str) -> str:
        """GitHub URL は任意。値があるときだけ ``https://github.com/`` 始まりを要求する。"""
        stripped = value.strip()
        if stripped and not stripped.startswith(_GITHUB_URL_PREFIX):
            raise ValueError(get_error("validation.github_url_invalid"))
        return value


class ResumeCreate(ResumeBase):
    pass


class ResumeUpdate(ResumeBase):
    pass


class ResumeResponse(ResumeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "updated_at")
    def serialize_as_jst(self, dt: datetime) -> str:
        """UTC datetime を JST (UTC+9) の ISO 8601 文字列にシリアライズする。"""
        return to_jst(dt).isoformat()


class ResumePreviewResponse(BaseModel):
    """保存前プレビュー（左右 diff 表示）用の整形済み HTML と画面用 CSS。

    DB を更新せず、編集中 payload を PDF と同じレイアウトに整形した HTML を返す。
    HTML 内の各値ノードには form パス（``data-fp``）が付与され、FE が変更箇所の
    ハイライト・スクロール先特定に使う。
    """

    html: str
    css: str
