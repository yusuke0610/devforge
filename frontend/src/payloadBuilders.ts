import { VALIDATION_MESSAGES } from "./constants/messages";
import type {
  CapitalUnit,
  Client,
  Experience,
  Project,
  ProjectPeriod,
  ProjectTeam,
  ResumeCreate,
  ResumeQualificationItem,
  TeamMember,
  TechnologyStackItem,
} from "./api/types";

export type TeamMemberForm = {
  role: string;
  count: string;
};

export type CareerProjectPeriodForm = {
  start_date: string;
  end_date: string;
  is_current: boolean;
};

export type CareerProjectForm = {
  name: string;
  periods: CareerProjectPeriodForm[];
  role: string;
  description: string;
  team: {
    total: string;
    members: TeamMemberForm[];
  };
  technology_stacks: TechnologyStackItem[];
  phases: string[];
};

export type CareerClientForm = {
  name: string;
  has_client: boolean;
  projects: CareerProjectForm[];
  is_vacation: boolean;
  vacation_start_date: string;
  vacation_end_date: string;
  vacation_is_current: boolean;
  vacation_description: string;
};

export type CareerExperienceForm = {
  company: string;
  business_description: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  employee_count: string;
  capital: string;
  capital_unit: CapitalUnit;
  is_it_company: boolean;
  description: string;
  clients: CareerClientForm[];
};

export type CareerFormState = {
  full_name: string;
  career_summary: string;
  self_pr: string;
  experiences: CareerExperienceForm[];
  qualifications: ResumeQualificationItem[];
};

/**
 * バリデーション失敗フィールドの位置情報。
 * すべて元の `CareerFormState` の index を指し、保存時のフォーカス・赤枠表示に使う。
 * プロジェクト配下（project）は `ProjectModal` を開いてから期間入力をフォーカスするため、
 * exp/client/proj/period の各 index を保持する。
 */
export type CareerFieldLocator =
  | { kind: "full_name" }
  | { kind: "career_summary" }
  | { kind: "self_pr" }
  | {
      kind: "experience";
      expIndex: number;
      field: "company" | "business_description" | "start_date" | "end_date" | "description";
    }
  | {
      kind: "vacation";
      expIndex: number;
      clientIndex: number;
      field: "start_date" | "end_date";
    }
  | {
      kind: "project";
      expIndex: number;
      clientIndex: number;
      projIndex: number;
      periodIndex: number;
      field: "start_date" | "end_date";
    }
  | { kind: "qualification"; index: number; field: "name" | "acquired_date" };

/** バリデーション結果。エラーが無ければ null。 */
export type CareerValidationError = {
  message: string;
  locator: CareerFieldLocator;
};

export function hasAnyText(values: Array<string | null | undefined>): boolean {
  return values.some((value) => Boolean(value?.trim()));
}

/** 終了日が開始日より前の場合にエラーメッセージを返す */
export function validateDateRange(
  startDate: string,
  endDate: string,
  isCurrent: boolean,
): string | null {
  if (isCurrent || !startDate || !endDate) return null;
  if (endDate < startDate) return VALIDATION_MESSAGES.DATE_RANGE_INVALID;
  return null;
}

/** periods 配列内にエラーがあれば最初のエラーメッセージを返す */
export function validatePeriods(periods: CareerProjectPeriodForm[]): string | null {
  for (const p of periods) {
    const err = validateDateRange(p.start_date, p.end_date, p.is_current);
    if (err) return err;
  }
  return null;
}

/**
 * payload に含める／バリデーション対象とする職務経歴かを判定する。
 * 会社名・事業内容・開始・終了のいずれかに入力があれば「内容あり」とみなす。
 * （end_date は在職中なら空として扱い、builder の正規化と基準を揃える）
 */
export function experienceIncluded(exp: CareerExperienceForm): boolean {
  const end = exp.is_current ? "" : exp.end_date;
  return hasAnyText([exp.company, exp.business_description, exp.start_date, end]);
}

/** payload に含める／バリデーション対象とするプロジェクトかを判定する。 */
export function projectIncluded(proj: CareerProjectForm): boolean {
  return hasAnyText([proj.name, proj.description]);
}

/**
 * payload に含める／バリデーション対象とする取引先かを判定する。
 * 休暇は期間・詳細のいずれかに入力があれば対象。通常取引先は
 * 「取引先なし」または呼称入力あり、または内容のあるプロジェクトを持つ場合に対象。
 */
export function clientIncluded(client: CareerClientForm): boolean {
  if (client.is_vacation) {
    const end = client.vacation_is_current ? "" : client.vacation_end_date;
    return hasAnyText([client.vacation_start_date, end, client.vacation_description]);
  }
  const name = client.has_client ? client.name : "";
  const hasProjects = client.projects.some(projectIncluded);
  return !client.has_client || Boolean(name.trim()) || hasProjects;
}

function buildTeam(team: CareerProjectForm["team"]): ProjectTeam {
  const members: TeamMember[] = team.members
    .filter((m) => m.role.trim() && String(m.count).trim())
    .map((m) => ({ role: m.role.trim(), count: Number(m.count) }));
  return {
    total: team.total.trim(),
    members,
  };
}

function buildPeriod(p: CareerProjectPeriodForm): ProjectPeriod {
  return {
    start_date: p.start_date.trim(),
    end_date: p.is_current ? "" : p.end_date.trim(),
    is_current: p.is_current,
  };
}

function buildProject(proj: CareerProjectForm): Project {
  return {
    name: proj.name.trim(),
    periods: proj.periods.map(buildPeriod),
    role: proj.role.trim(),
    description: proj.description.trim(),
    team: buildTeam(proj.team),
    technology_stacks: proj.technology_stacks
      .map((stack) => ({
        category: stack.category,
        name: stack.name.trim(),
      }))
      .filter((stack) => Boolean(stack.name)),
    phases: proj.phases.filter((p) => Boolean(p)),
  };
}

function buildClient(client: CareerClientForm): Client {
  if (client.is_vacation) {
    return {
      name: "",
      has_client: client.has_client,
      projects: [],
      is_vacation: true,
      vacation_start_date: client.vacation_start_date.trim(),
      vacation_end_date: client.vacation_is_current ? "" : client.vacation_end_date.trim(),
      vacation_is_current: client.vacation_is_current,
      vacation_description: client.vacation_description.trim(),
    };
  }
  return {
    name: client.has_client ? client.name.trim() : "",
    has_client: client.has_client,
    projects: client.projects.filter(projectIncluded).map(buildProject),
    is_vacation: false,
    vacation_start_date: "",
    vacation_end_date: "",
    vacation_is_current: false,
    vacation_description: "",
  };
}

function buildExperience(exp: CareerExperienceForm): Experience {
  return {
    company: exp.company.trim(),
    business_description: exp.business_description.trim(),
    start_date: exp.start_date.trim(),
    end_date: exp.is_current ? "" : exp.end_date.trim(),
    is_current: exp.is_current,
    employee_count: exp.employee_count.trim(),
    capital: exp.capital.trim(),
    capital_unit: exp.capital_unit,
    is_it_company: exp.is_it_company,
    description: exp.is_it_company ? "" : exp.description.trim(),
    clients: exp.is_it_company ? exp.clients.filter(clientIncluded).map(buildClient) : [],
  };
}

/**
 * 職務経歴フォームを走査し、最初に見つかった必須・日付エラーを locator 付きで返す。
 * エラーが無ければ null。`buildCareerPayload` が投げていた検査をここに集約し、
 * 保存時のフォーカス・赤枠表示に使えるよう「どのフィールドか」を返す。
 *
 * 検査順序とメッセージは従来の `buildCareerPayload` と完全に一致させている
 * （氏名 → 職務要約 → 自己PR → 職務経歴 → 資格）。index はすべて元フォームのもの。
 */
export function validateCareerForm(state: CareerFormState): CareerValidationError | null {
  if (!state.full_name.trim()) {
    return { message: VALIDATION_MESSAGES.FULL_NAME_REQUIRED, locator: { kind: "full_name" } };
  }
  if (!state.career_summary.trim()) {
    return {
      message: VALIDATION_MESSAGES.CAREER_SUMMARY_REQUIRED,
      locator: { kind: "career_summary" },
    };
  }
  if (!state.self_pr.trim()) {
    return { message: VALIDATION_MESSAGES.SELF_PR_REQUIRED, locator: { kind: "self_pr" } };
  }

  for (let expIndex = 0; expIndex < state.experiences.length; expIndex += 1) {
    const exp = state.experiences[expIndex];
    // 空欄だけの経歴は payload から除外されるためバリデーション対象外。
    if (!experienceIncluded(exp)) continue;

    const company = exp.company.trim();
    const business = exp.business_description.trim();
    const start = exp.start_date.trim();
    const end = exp.is_current ? "" : exp.end_date.trim();

    if (!company) {
      return {
        message: VALIDATION_MESSAGES.EXPERIENCE_REQUIRED_FIELDS,
        locator: { kind: "experience", expIndex, field: "company" },
      };
    }
    if (!business) {
      return {
        message: VALIDATION_MESSAGES.EXPERIENCE_REQUIRED_FIELDS,
        locator: { kind: "experience", expIndex, field: "business_description" },
      };
    }
    if (!start) {
      return {
        message: VALIDATION_MESSAGES.EXPERIENCE_REQUIRED_FIELDS,
        locator: { kind: "experience", expIndex, field: "start_date" },
      };
    }
    if (!exp.is_current && !end) {
      return {
        message: VALIDATION_MESSAGES.EXPERIENCE_END_DATE_REQUIRED,
        locator: { kind: "experience", expIndex, field: "end_date" },
      };
    }
    if (!exp.is_current && start && end && end < start) {
      return {
        message: VALIDATION_MESSAGES.DATE_RANGE_INVALID,
        locator: { kind: "experience", expIndex, field: "end_date" },
      };
    }

    if (!exp.is_it_company) {
      if (!exp.description.trim()) {
        return {
          message: VALIDATION_MESSAGES.EXPERIENCE_DESCRIPTION_REQUIRED,
          locator: { kind: "experience", expIndex, field: "description" },
        };
      }
      continue;
    }

    for (let clientIndex = 0; clientIndex < exp.clients.length; clientIndex += 1) {
      const client = exp.clients[clientIndex];
      if (!clientIncluded(client)) continue;

      if (client.is_vacation) {
        const vs = client.vacation_start_date.trim();
        const ve = client.vacation_is_current ? "" : client.vacation_end_date.trim();
        if (!vs) {
          return {
            message: VALIDATION_MESSAGES.VACATION_START_DATE_REQUIRED,
            locator: { kind: "vacation", expIndex, clientIndex, field: "start_date" },
          };
        }
        if (!client.vacation_is_current && !ve) {
          return {
            message: VALIDATION_MESSAGES.VACATION_END_DATE_REQUIRED,
            locator: { kind: "vacation", expIndex, clientIndex, field: "end_date" },
          };
        }
        if (!client.vacation_is_current && vs && ve && ve < vs) {
          return {
            message: VALIDATION_MESSAGES.DATE_RANGE_INVALID,
            locator: { kind: "vacation", expIndex, clientIndex, field: "end_date" },
          };
        }
        continue;
      }

      for (let projIndex = 0; projIndex < client.projects.length; projIndex += 1) {
        const proj = client.projects[projIndex];
        if (!projectIncluded(proj)) continue;

        // 内容のあるプロジェクトは periods が 1 件以上あり、各期間の開始年月が必須。
        if (proj.periods.length === 0) {
          return {
            message: VALIDATION_MESSAGES.PROJECT_START_DATE_REQUIRED,
            locator: { kind: "project", expIndex, clientIndex, projIndex, periodIndex: 0, field: "start_date" },
          };
        }
        for (let periodIndex = 0; periodIndex < proj.periods.length; periodIndex += 1) {
          const period = proj.periods[periodIndex];
          const ps = period.start_date.trim();
          const pe = period.is_current ? "" : period.end_date.trim();
          if (!ps) {
            return {
              message: VALIDATION_MESSAGES.PROJECT_START_DATE_REQUIRED,
              locator: { kind: "project", expIndex, clientIndex, projIndex, periodIndex, field: "start_date" },
            };
          }
          if (!period.is_current && !pe) {
            return {
              message: VALIDATION_MESSAGES.PROJECT_END_DATE_REQUIRED,
              locator: { kind: "project", expIndex, clientIndex, projIndex, periodIndex, field: "end_date" },
            };
          }
          if (!period.is_current && ps && pe && pe < ps) {
            return {
              message: VALIDATION_MESSAGES.DATE_RANGE_INVALID,
              locator: { kind: "project", expIndex, clientIndex, projIndex, periodIndex, field: "end_date" },
            };
          }
        }
      }
    }
  }

  for (let index = 0; index < state.qualifications.length; index += 1) {
    const q = state.qualifications[index];
    const acquired = q.acquired_date.trim();
    const name = q.name.trim();
    if (!hasAnyText([acquired, name])) continue;
    if (!acquired) {
      return {
        message: VALIDATION_MESSAGES.QUALIFICATION_REQUIRED_FIELDS,
        locator: { kind: "qualification", index, field: "acquired_date" },
      };
    }
    if (!name) {
      return {
        message: VALIDATION_MESSAGES.QUALIFICATION_REQUIRED_FIELDS,
        locator: { kind: "qualification", index, field: "name" },
      };
    }
  }

  return null;
}

export function buildCareerPayload(state: CareerFormState): ResumeCreate {
  // バリデーションは validateCareerForm に集約。失敗時は従来同様メッセージを throw する。
  const validation = validateCareerForm(state);
  if (validation) {
    throw new Error(validation.message);
  }

  const experiences: Experience[] = state.experiences
    .filter(experienceIncluded)
    .map(buildExperience);

  const qualifications: ResumeQualificationItem[] = state.qualifications
    .map((q) => ({
      acquired_date: q.acquired_date.trim(),
      name: q.name.trim(),
    }))
    .filter((q) => hasAnyText([q.acquired_date, q.name]));

  return {
    full_name: state.full_name.trim(),
    career_summary: state.career_summary.trim(),
    self_pr: state.self_pr.trim(),
    experiences,
    qualifications,
  };
}
