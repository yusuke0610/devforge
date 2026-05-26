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

export type CareerProject = {
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  role: string;
  challenge: string;
  action: string;
  result: string;
  team: ProjectTeam;
  technology_stacks: CareerTechnologyStack[];
  phases: string[];
};

export type CareerClient = {
  name: string;
  has_client: boolean;
  projects: CareerProject[];
};

export type CareerExperience = {
  company: string;
  business_description: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  employee_count: string;
  capital: string;
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
