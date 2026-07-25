import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
  blankCareerProjectPeriod,
  blankCareerTechnologyStack,
  blankResumeQualification,
} from "./constants";
import type { CareerFormState } from "./payloadBuilders";
import type { ResumeDraftResultResponse, ResumeResponse } from "./api/types";

/**
 * フォーム注入の入力型（#524 汎用化 / ADR-0025）。`mapCareerResumeToForm` は保存済み経歴書
 * （ResumeResponse）と、ドラフト生成 payload（ResumeDraftResultResponse）の両方を受け取る。
 * マッパーは created_at / updated_at を参照しないため、timestamps を除いた共通形で受ける。
 */
export type ResumeFormSource = Omit<ResumeResponse, "created_at" | "updated_at"> | ResumeDraftResultResponse;

export function createInitialCareerForm(): CareerFormState {
  return {
    full_name: "",
    email: "",
    github_url: "",
    career_summary: "",
    self_pr: "",
    experiences: [{ ...blankCareerExperience }],
    qualifications: [{ ...blankResumeQualification }],
  };
}

// 生成型（ResumeResponse）では list 系フィールドが optional（backend の default_factory 由来、
// team も optional）なため、配列アクセスは `?? []`、team は `?.` で null 安全化する（ADR-0007 論点B）。
export function mapCareerResumeToForm(response: ResumeFormSource): CareerFormState {
  const experiences = response.experiences ?? [];
  const qualifications = response.qualifications ?? [];
  return {
    full_name: response.full_name,
    email: response.email,
    github_url: response.github_url ?? "",
    career_summary: response.career_summary,
    self_pr: response.self_pr,
    experiences:
      experiences.length > 0
        ? experiences.map((experience) => ({
          ...experience,
          is_it_company: experience.is_it_company ?? true,
          description: experience.description ?? "",
          clients:
            (experience.clients ?? []).length > 0
              ? (experience.clients ?? []).map((client) => ({
                ...client,
                is_vacation: client.is_vacation ?? false,
                vacation_start_date: client.vacation_start_date ?? "",
                vacation_end_date: client.vacation_end_date ?? "",
                vacation_is_current: client.vacation_is_current ?? false,
                vacation_description: client.vacation_description ?? "",
                projects:
                  (client.projects ?? []).length > 0
                    ? (client.projects ?? []).map((project) => ({
                      ...project,
                      periods: (project.periods ?? []).length > 0
                        ? (project.periods ?? [])
                        : [{ ...blankCareerProjectPeriod }],
                      team: {
                        total: project.team?.total ?? "",
                        members: (project.team?.members ?? []).map((member) => ({
                          ...member,
                          count: String(member.count),
                        })),
                      },
                      technology_stacks:
                        (project.technology_stacks ?? []).length > 0
                          ? (project.technology_stacks ?? [])
                          : [{ ...blankCareerTechnologyStack }],
                      phases: project.phases ?? [],
                    }))
                    : [{ ...blankCareerProject, technology_stacks: [{ ...blankCareerTechnologyStack }] }],
              }))
              : [{ ...blankCareerClient }],
        }))
        : [{ ...blankCareerExperience }],
    qualifications:
      qualifications.length > 0
        ? qualifications
        : [{ ...blankResumeQualification }],
  };
}
