"""DevForge Agent（LLM チャット）の Pydantic スキーマ（ADR-0010）。

リクエストの ``resume`` は保存用の ``ResumeCreate`` ではなく緩い専用コンテキスト型を使う。
ユーザーが編集途中のフォーム（必須項目が未入力・日付未設定など保存契約を満たさない状態）
から Agent を呼べる必要があり、保存時バリデーションを再利用すると 422 になるため。
フィールドの max_length は保存契約（``resume.py``）と同じ上限に揃える。

レスポンスの ``operations`` はテキストフィールドの置換のみ（構造編集なし）。
スコープ選択が必須で対象の位置はリクエストで確定するため、operation は
パス指定を持たず「フィールド名 + 新しい値」だけを返す。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.messages import get_error

AgentScope = Literal["project", "career_summary", "self_pr", "experience"]

# 使用する LLM モデルのエイリアス。ADR-0023 で Haiku 無料一本化へ縮退したため haiku のみ。
# 実モデル ID は services/agent/model_catalog.py の MODEL_CATALOG が正本（キー集合を一致させる）。
AgentModelAlias = Literal["haiku"]


class AgentTechnologyStack(BaseModel):
    """LLM コンテキスト用の技術スタック（保存契約より緩い）。"""

    category: str = Field(default="", max_length=60)
    name: str = Field(default="", max_length=120)


class AgentProjectContext(BaseModel):
    """LLM コンテキスト用のプロジェクト情報。"""

    name: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4500)
    technology_stacks: list[AgentTechnologyStack] = Field(default_factory=list)
    phases: list[str] = Field(default_factory=list)


class AgentClientContext(BaseModel):
    """LLM コンテキスト用の取引先情報。"""

    name: str = Field(default="", max_length=200)
    projects: list[AgentProjectContext] = Field(default_factory=list)


class AgentExperienceContext(BaseModel):
    """LLM コンテキスト用の在籍企業情報。"""

    company: str = Field(default="", max_length=120)
    business_description: str = Field(default="", max_length=200)
    # experience スコープで編集対象となる自由記述欄（非IT企業の職務詳細）
    description: str = Field(default="", max_length=4500)
    # IT企業かどうか（experience スコープのプロンプト分岐に使用）
    is_it_company: bool = True
    clients: list[AgentClientContext] = Field(default_factory=list)


class AgentResumeContext(BaseModel):
    """LLM に渡す編集中の職務経歴書コンテキスト。

    保存契約（必須項目・日付検証）は適用しない。DB は参照せず、
    フロントが編集中のフォーム内容をそのまま送る設計（DB を更新しない原則）。
    """

    career_summary: str = Field(default="", max_length=2000)
    self_pr: str = Field(default="", max_length=2000)
    experiences: list[AgentExperienceContext] = Field(default_factory=list)


class ProjectTarget(BaseModel):
    """scope=project のとき対象プロジェクトを特定するインデックス。"""

    experience_index: int = Field(ge=0)
    client_index: int = Field(ge=0)
    project_index: int = Field(ge=0)


class ExperienceTarget(BaseModel):
    """scope=experience のとき対象在籍企業を特定するインデックス。

    ``extra="forbid"`` により ProjectTarget の 3 キー payload は
    ExperienceTarget にマッチしない（union で型を決定的に区別するため）。
    """

    model_config = ConfigDict(extra="forbid")

    experience_index: int = Field(ge=0)


class AgentHistoryEntry(BaseModel):
    """マルチターン用の会話履歴 1 件。

    user はユーザーの依頼文のみ（レジュメコンテキストは含めない。コンテキストは
    最新ターンの prompt にのみ載せ、毎ターンの重複でトークンが膨れるのを防ぐ）。
    assistant は前回 LLM が返した JSON 文字列をそのまま入れる（出力形式の実例として
    few-shot 的に働き、小型モデルのフォーマット逸脱を抑える狙い）。
    """

    role: Literal["user", "assistant"]
    text: str = Field(min_length=1, max_length=6000)


class AgentChatRequest(BaseModel):
    """Agent チャットのリクエスト。スコープ選択は必須。"""

    scope: AgentScope
    prompt: str = Field(min_length=1, max_length=2000)
    # 使用モデル。ADR-0023 で課金を撤去したため全モデル無料（マルチプロバイダは #523 で縮退予定）。
    # デフォルト haiku で既存クライアントと後方互換
    model: AgentModelAlias = "haiku"
    resume: AgentResumeContext
    # project は ProjectTarget | ExperienceTarget | None の union（ProjectTarget を先に配置）。
    # ExperienceTarget は extra="forbid" により 3 キー payload がマッチしないため
    # union の解決は決定的。project スコープは ProjectTarget 必須、experience は ExperienceTarget 必須。
    target: ProjectTarget | ExperienceTarget | None = None
    # 直近 3 往復（6 エントリ）まで。サーバーはセッションを持たずフロントが送る
    history: list[AgentHistoryEntry] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_target(self) -> "AgentChatRequest":
        """project / experience スコープでは対象の指定を必須とする。"""
        if self.scope == "project" and not isinstance(self.target, ProjectTarget):
            raise ValueError(get_error("agent.target_required"))
        if self.scope == "experience" and not isinstance(self.target, ExperienceTarget):
            raise ValueError(get_error("agent.target_required"))
        return self


class ResumeDraftRequest(BaseModel):
    """経歴書ドラフト生成（ADR-0018）のリクエスト。

    生成対象（リポジトリ集合）はサーバー側が連携キャッシュから決めるため、
    クライアントが指定するのは使用モデルのみ。
    """

    # 使用モデル。既定は haiku（ADR-0023 で課金撤去済み・全モデル無料）
    model: AgentModelAlias = "haiku"


class AgentOperation(BaseModel):
    """resume state へ適用する差分（テキストフィールドの置換）。

    フロントは選択済みスコープ（と target）に対応するフィールドへ value を反映する。
    DB は更新せず、ユーザーが「適用」した時点で既存の保存 API を呼ぶ。

    ``field`` は意図的に Literal ではなく str で受ける。小型 LLM が許可外の
    field 名を返すことがあり、Literal だと operation 1 件の逸脱でレスポンス全体が
    ValidationError になる。許可 field の検証・破棄は chat_service._parse_response が担う。
    """

    field: str = Field(max_length=120)
    value: str = Field(max_length=4500)


class AgentChatResponse(BaseModel):
    """Agent チャットのレスポンス（AI の説明文 + 差分 operations）。

    ``suggestions`` は依頼が曖昧で operations を返せないときに LLM が生成する
    「次の依頼文の候補」。フロントはボタンとして表示し、押下されたテキストを
    そのまま次の ``prompt`` として再送信する。検証・件数制限は
    chat_service._parse_response が担う。
    """

    message: str
    operations: list[AgentOperation] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ResumeImportExperience(BaseModel):
    """PDF から抽出した職歴 1 件（フラット / ADR-0024 v1）。

    フォーム注入用のため全フィールド任意（欠落は空文字）。深いネスト（clients /
    projects / periods / technology_stacks）は v1 では抽出せず、ユーザーがフォームで追記する。
    """

    company: str = ""
    business_description: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class ResumeImportResponse(BaseModel):
    """手持ち PDF 経歴書の抽出結果（ADR-0024）。

    Resume 互換のフォーム注入用 payload。保存契約（schemas/resume.py の strict な
    バリデーション）とは分離し、抽出できた分だけを返す（全フィールド任意・欠落は空）。
    DB は更新せず、フロントがフォーム state へ注入 → ユーザー確認 → 既存の保存 API を呼ぶ。
    email 等の未抽出フィールドはフォームでユーザーが補完する。
    """

    full_name: str = ""
    career_summary: str = ""
    self_pr: str = ""
    experiences: list[ResumeImportExperience] = Field(default_factory=list)
