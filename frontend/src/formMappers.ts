import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
  blankCareerProjectPeriod,
  blankCareerTechnologyStack,
  blankResumeQualification,
} from "./constants";
import type { CareerFormState } from "./payloadBuilders";
import type { CareerResumeResponse } from "./types";

export function createInitialCareerForm(): CareerFormState {
  return {
    full_name: "",
    career_summary: "",
    self_pr: "",
    experiences: [{ ...blankCareerExperience }],
    qualifications: [{ ...blankResumeQualification }],
  };
}

export function mapCareerResumeToForm(response: CareerResumeResponse): CareerFormState {
  return {
    full_name: response.full_name,
    career_summary: response.career_summary,
    self_pr: response.self_pr,
    experiences:
      response.experiences.length > 0
        ? response.experiences.map((experience) => ({
          ...experience,
          is_it_company: experience.is_it_company ?? true,
          description: experience.description ?? "",
          clients:
            experience.clients.length > 0
              ? experience.clients.map((client) => ({
                ...client,
                is_vacation: client.is_vacation ?? false,
                vacation_start_date: client.vacation_start_date ?? "",
                vacation_end_date: client.vacation_end_date ?? "",
                vacation_is_current: client.vacation_is_current ?? false,
                vacation_description: client.vacation_description ?? "",
                projects:
                  client.projects.length > 0
                    ? client.projects.map((project) => ({
                      ...project,
                      periods: project.periods.length > 0
                        ? project.periods
                        : [{ ...blankCareerProjectPeriod }],
                      team: {
                        total: project.team.total ?? "",
                        members: project.team.members.map((member) => ({
                          ...member,
                          count: String(member.count),
                        })),
                      },
                      technology_stacks:
                        project.technology_stacks.length > 0
                          ? project.technology_stacks
                          : [{ ...blankCareerTechnologyStack }],
                      phases: project.phases ?? [],
                    }))
                    : [{ ...blankCareerProject, technology_stacks: [{ ...blankCareerTechnologyStack }] }],
              }))
              : [{ ...blankCareerClient }],
        }))
        : [{ ...blankCareerExperience }],
    qualifications:
      response.qualifications.length > 0
        ? response.qualifications
        : [{ ...blankResumeQualification }],
  };
}
