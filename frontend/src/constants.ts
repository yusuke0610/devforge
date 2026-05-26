import type { CareerTechnologyStackCategory, ResumeQualification } from "./types";
import type {
  CareerClientForm,
  CareerExperienceForm,
  CareerProjectForm,
  TeamMemberForm,
} from "./payloadBuilders";
import type { CareerTechnologyStack } from "./types";

export const blankResumeQualification: ResumeQualification = {
  acquired_date: "",
  name: "",
};

export const careerTechnologyStackCategories: CareerTechnologyStackCategory[] = [
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

export const careerTechnologyStackCategoryLabels: Record<CareerTechnologyStackCategory, string> = {
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

export const blankCareerTechnologyStack: CareerTechnologyStack = {
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
  "総合テスト",
  "統合テスト",
  "リリース",
  "運用保守",
  "運用監視",
];

export const blankTeamMember: TeamMemberForm = {
  role: "",
  count: "",
};

export const blankCareerProject: CareerProjectForm = {
  name: "",
  start_date: "",
  end_date: "",
  is_current: false,
  role: "",
  challenge: "",
  action: "",
  result: "",
  team: { total: "", members: [] },
  technology_stacks: [{ ...blankCareerTechnologyStack }],
  phases: [],
};

export const blankCareerClient: CareerClientForm = {
  name: "",
  has_client: true,
  projects: [{ ...blankCareerProject, technology_stacks: [{ ...blankCareerTechnologyStack }] }],
};

export const blankCareerExperience: CareerExperienceForm = {
  company: "",
  business_description: "",
  start_date: "",
  end_date: "",
  is_current: false,
  employee_count: "",
  capital: "",
  clients: [{ ...blankCareerClient }],
};
