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
    projects: client.projects
      .map(buildProject)
      .filter((p) => hasAnyText([p.name, p.description])),
    is_vacation: false,
    vacation_start_date: "",
    vacation_end_date: "",
    vacation_is_current: false,
    vacation_description: "",
  };
}

export function buildCareerPayload(state: CareerFormState): ResumeCreate {
  const full_name = state.full_name.trim();
  if (!full_name) {
    throw new Error(VALIDATION_MESSAGES.FULL_NAME_REQUIRED);
  }

  const career_summary = state.career_summary.trim();
  if (!career_summary) {
    throw new Error(VALIDATION_MESSAGES.CAREER_SUMMARY_REQUIRED);
  }

  const self_pr = state.self_pr.trim();
  if (!self_pr) {
    throw new Error(VALIDATION_MESSAGES.SELF_PR_REQUIRED);
  }

  const experiences: Experience[] = state.experiences
    .map((exp) => ({
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
      clients: exp.is_it_company
        ? exp.clients
            .map(buildClient)
            .filter((c) =>
              c.is_vacation
                ? hasAnyText([c.vacation_start_date, c.vacation_end_date, c.vacation_description])
                : !c.has_client || c.name.trim() || (c.projects ?? []).length > 0,
            )
        : [],
    }))
    .filter((exp) =>
      hasAnyText([exp.company, exp.business_description, exp.start_date, exp.end_date]),
    );

  for (const exp of experiences) {
    if (!exp.company || !exp.business_description || !exp.start_date) {
      throw new Error(VALIDATION_MESSAGES.EXPERIENCE_REQUIRED_FIELDS);
    }
    if (!exp.is_current && !exp.end_date) {
      throw new Error(VALIDATION_MESSAGES.EXPERIENCE_END_DATE_REQUIRED);
    }
    if (!exp.is_current && exp.start_date && exp.end_date && exp.end_date < exp.start_date) {
      throw new Error(VALIDATION_MESSAGES.DATE_RANGE_INVALID);
    }
    if (!exp.is_it_company) {
      if (!exp.description) {
        throw new Error(VALIDATION_MESSAGES.EXPERIENCE_DESCRIPTION_REQUIRED);
      }
      continue;
    }
    for (const client of exp.clients ?? []) {
      if (client.is_vacation) {
        if (!client.vacation_start_date) {
          throw new Error(VALIDATION_MESSAGES.VACATION_START_DATE_REQUIRED);
        }
        if (!client.vacation_is_current && !client.vacation_end_date) {
          throw new Error(VALIDATION_MESSAGES.VACATION_END_DATE_REQUIRED);
        }
        if (
          !client.vacation_is_current &&
          client.vacation_start_date &&
          client.vacation_end_date &&
          client.vacation_end_date < client.vacation_start_date
        ) {
          throw new Error(VALIDATION_MESSAGES.DATE_RANGE_INVALID);
        }
        continue;
      }
      for (const proj of client.projects ?? []) {
        // 内容のあるプロジェクトは periods が 1 件以上あり、各期間の開始年月が必須。
        if ((proj.periods ?? []).length === 0) {
          throw new Error(VALIDATION_MESSAGES.PROJECT_START_DATE_REQUIRED);
        }
        for (const period of proj.periods ?? []) {
          if (!period.start_date) {
            throw new Error(VALIDATION_MESSAGES.PROJECT_START_DATE_REQUIRED);
          }
          if (!period.is_current && !period.end_date) {
            throw new Error(VALIDATION_MESSAGES.PROJECT_END_DATE_REQUIRED);
          }
          if (
            !period.is_current &&
            period.start_date &&
            period.end_date &&
            period.end_date < period.start_date
          ) {
            throw new Error(VALIDATION_MESSAGES.DATE_RANGE_INVALID);
          }
        }
      }
    }
  }

  const qualifications: ResumeQualificationItem[] = state.qualifications
    .map((q) => ({
      acquired_date: q.acquired_date.trim(),
      name: q.name.trim(),
    }))
    .filter((q) => hasAnyText([q.acquired_date, q.name]));

  for (const q of qualifications) {
    if (!q.acquired_date || !q.name) {
      throw new Error(VALIDATION_MESSAGES.QUALIFICATION_REQUIRED_FIELDS);
    }
  }

  return {
    full_name,
    career_summary,
    self_pr,
    experiences,
    qualifications,
  };
}
