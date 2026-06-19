import type {
  CapitalUnit,
  ResumeQualificationItem,
  TechnologyStackCategory,
  TechnologyStackItem,
} from "./api/types";
import type {
  CareerClientForm,
  CareerExperienceForm,
  CareerProjectForm,
  CareerProjectPeriodForm,
  TeamMemberForm,
} from "./payloadBuilders";

export const blankResumeQualification: ResumeQualificationItem = {
  acquired_date: "",
  name: "",
};

/** 資本金の単位の選択肢（ドロップダウン表示順）。backend の Literal と手動同期。 */
export const CAPITAL_UNITS: readonly CapitalUnit[] = ["万円", "百万円", "千万円", "億円"];

/** 資本金の単位の既定値（後方互換のため「千万円」）。 */
export const DEFAULT_CAPITAL_UNIT: CapitalUnit = "千万円";

export const careerTechnologyStackCategories: TechnologyStackCategory[] = [
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
];

export const careerTechnologyStackCategoryLabels: Record<TechnologyStackCategory, string> = {
  language: "言語",
  framework: "FW",
  os: "OS",
  db: "DB",
  cloud_provider: "クラウド",
  container: "コンテナ",
  iac: "IaC",
  vcs: "バージョン管理",
  ci_cd: "CI/CD",
  project_tool: "プロジェクトツール",
  monitoring: "監視ツール",
  middleware: "ミドルウェア",
  ai_agent: "AIエージェント",
};

export const blankCareerTechnologyStack: TechnologyStackItem = {
  category: "language",
  name: "",
};

export const teamRoleOptions = [
  "PM",
  "PL",
  "PMO",
  "SM",
  "SE",
  "PG",
  "テスター",
  "デザイナー",
  "インフラ",
  "その他",
];

export const phaseOptions = [
  "要件定義",
  "基本設計",
  "詳細設計",
  "開発",
  "単体テスト",
  "結合テスト",
  "総合テスト",
  "リリース",
  "運用保守",
  "運用監視",
];

export const blankTeamMember: TeamMemberForm = {
  role: "",
  count: "",
};

export const blankCareerProjectPeriod: CareerProjectPeriodForm = {
  start_date: "",
  end_date: "",
  is_current: false,
};

export const blankCareerProject: CareerProjectForm = {
  name: "",
  periods: [{ ...blankCareerProjectPeriod }],
  role: "",
  description: "",
  team: { total: "", members: [] },
  technology_stacks: [{ ...blankCareerTechnologyStack }],
  phases: [],
};

export const blankCareerClient: CareerClientForm = {
  name: "",
  has_client: true,
  projects: [{ ...blankCareerProject, technology_stacks: [{ ...blankCareerTechnologyStack }] }],
  is_vacation: false,
  vacation_start_date: "",
  vacation_end_date: "",
  vacation_is_current: false,
  vacation_description: "",
};

export const blankCareerExperience: CareerExperienceForm = {
  company: "",
  business_description: "",
  start_date: "",
  end_date: "",
  is_current: false,
  employee_count: "",
  capital: "",
  capital_unit: DEFAULT_CAPITAL_UNIT,
  is_it_company: true,
  description: "",
  clients: [{ ...blankCareerClient }],
};
