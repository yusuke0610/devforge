/**
 * backend Pydantic スキーマと対になる DTO 型定義。
 *
 * ## 同期ルール
 *
 * 本ファイルの DTO 型は backend `backend/app/schemas/`（blog.py / master_data.py / resume.py）
 * の Pydantic レスポンススキーマと構造を一致させる必要がある。言語境界のため codegen は未導入で、
 * 手動同期で運用している（エラーコードの `errorCodes.ts` ↔ `errors.py` と同じ方針）。
 *
 * - BE schema のフィールドを増減・rename → 対応する本ファイルの type も同時に更新すること
 * - 主な対応: `BlogArticle`↔`BlogArticleResponse`, `BlogAccount`↔`BlogAccountResponse`,
 *   `MasterItem`↔`MasterItem`, `TechStackMasterItem`↔`TechStackMasterItem`,
 *   Career 系 type ↔ `resume.py` の各 Item
 */
export type ResumeQualification = {
  acquired_date: string;
  name: string;
};

export type CareerTechnologyStackCategory =
  | "language"
  | "framework"
  | "os"
  | "db"
  | "cloud_provider"
  | "container"
  | "iac"
  | "vcs"
  | "ci_cd"
  | "project_tool"
  | "monitoring"
  | "middleware"
  | "ai_agent";

export type CareerTechnologyStack = {
  category: CareerTechnologyStackCategory;
  name: string;
};

export type TeamMember = {
  role: string;
  count: number;
};

export type ProjectTeam = {
  total: string;
  members: TeamMember[];
};

export type ProjectPeriod = {
  start_date: string;
  end_date: string;
  is_current: boolean;
};

export type CareerProject = {
  name: string;
  periods: ProjectPeriod[];
  role: string;
  /** 課題・行動・成果を統合した自由記述欄（見出し「詳細」） */
  description: string;
  team: ProjectTeam;
  technology_stacks: CareerTechnologyStack[];
  phases: string[];
};

export type CareerClient = {
  name: string;
  has_client: boolean;
  projects: CareerProject[];
  /** 休暇エントリか。true のとき取引先ではなく在籍中の休暇を表し vacation_* を使う。 */
  is_vacation: boolean;
  vacation_start_date: string;
  vacation_end_date: string;
  vacation_is_current: boolean;
  vacation_description: string;
};

/** 資本金の単位。backend schemas/resume.py の Experience.capital_unit と対の DTO。 */
export type CapitalUnit = "万円" | "百万円" | "千万円" | "億円";

export type CareerExperience = {
  company: string;
  business_description: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  employee_count: string;
  capital: string;
  capital_unit: CapitalUnit;
  /** IT 企業かどうか。false（非IT）の場合は取引先/プロジェクトを持たず description を使う。 */
  is_it_company: boolean;
  /** 非IT企業の職務内容を記述する自由記述欄（見出し「詳細」）。 */
  description: string;
  clients: CareerClient[];
};

export type CareerResumePayload = {
  full_name: string;
  career_summary: string;
  self_pr: string;
  experiences: CareerExperience[];
  qualifications: ResumeQualification[];
};

export type CareerResumeResponse = CareerResumePayload & {
  id: string;
  created_at: string;
  updated_at: string;
};

export type MasterItem = {
  id: string;
  name: string;
  sort_order: number;
};

export type TechStackMasterItem = {
  id: string;
  category: string;
  name: string;
  sort_order: number;
};

export type BlogAccount = {
  id: string;
  platform: "zenn" | "note" | "qiita";
  username: string;
  last_synced_at: string | null;
  created_at: string;
};

export type BlogArticle = {
  id: string;
  platform: string;
  title: string;
  url: string;
  published_at: string | null;
  likes_count: number;
  summary: string | null;
  tags: string[];
};
