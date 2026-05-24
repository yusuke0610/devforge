import { VALIDATION_MESSAGES } from "./constants/messages";
import type {
  CareerClient,
  CareerExperience,
  CareerProject,
  CareerResumePayload,
  CareerTechnologyStack,
  ProjectTeam,
  ResumeQualification,
  TeamMember,
} from "./types";

export type TeamMemberForm = {
  role: string;
  count: string;
};

export type CareerProjectForm = {
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  role: string;
  description: string;
  challenge: string;
  action: string;
  result: string;
  team: {
    total: string;
    members: TeamMemberForm[];
  };
  technology_stacks: CareerTechnologyStack[];
  phases: string[];
};

export type CareerClientForm = {
  name: string;
  has_client: boolean;
  projects: CareerProjectForm[];
};

export type CareerExperienceForm = {
  company: string;
  business_description: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  employee_count: string;
  capital: string;
  clients: CareerClientForm[];
};

export type CareerFormState = {
  full_name: string;
  career_summary: string;
  self_pr: string;
  experiences: CareerExperienceForm[];
  qualifications: ResumeQualification[];
};

export function hasAnyText(values: Array<string | null | undefined>): boolean {
  return values.some((value) => Boolean(value?.trim()));
}

/** 終了日が開始日より前の場合にエラーメッセージを返す */
export function validateDateRange(startDate: string, endDate: string, isCurrent: boolean): string | null {
  if (isCurrent || !startDate || !endDate) return null;
  if (endDate < startDate) return VALIDATION_MESSAGES.DATE_RANGE_INVALID;
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

function buildProject(proj: CareerProjectForm): CareerProject {
  return {
    name: proj.name.trim(),
    start_date: proj.start_date.trim(),
    end_date: proj.is_current ? "" : proj.end_date.trim(),
    is_current: proj.is_current,
    role: proj.role.trim(),
    description: proj.description.trim(),
    challenge: proj.challenge.trim(),
    action: proj.action.trim(),
    result: proj.result.trim(),
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

function buildClient(client: CareerClientForm): CareerClient {
  return {
    name: client.has_client ? client.name.trim() : "",
    has_client: client.has_client,
    projects: client.projects
      .map(buildProject)
      .filter((p) => hasAnyText([p.name, p.description, p.challenge, p.action, p.result])),
  };
}

export function buildCareerPayload(state: CareerFormState): CareerResumePayload {
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

  const experiences: CareerExperience[] = state.experiences
    .map((exp) => ({
      company: exp.company.trim(),
      business_description: exp.business_description.trim(),
      start_date: exp.start_date.trim(),
      end_date: exp.is_current ? "" : exp.end_date.trim(),
      is_current: exp.is_current,
      employee_count: exp.employee_count.trim(),
      capital: exp.capital.trim(),
      clients: exp.clients
        .map(buildClient)
        .filter((c) => !c.has_client || c.name.trim() || c.projects.length > 0),
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
    for (const client of exp.clients) {
      for (const proj of client.projects) {
        if (!proj.is_current && proj.start_date && proj.end_date && proj.end_date < proj.start_date) {
          throw new Error(VALIDATION_MESSAGES.DATE_RANGE_INVALID);
        }
      }
    }
  }

  const qualifications: ResumeQualification[] = state.qualifications
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
