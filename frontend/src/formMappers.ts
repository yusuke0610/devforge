import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
  blankCareerTechnologyStack,
  blankResumeQualification,
} from "./constants";
import type {
  CareerExperienceForm,
  CareerFormState,
  CareerProjectForm,
} from "./payloadBuilders";
import type { CareerResumePayload, CareerResumeResponse } from "./types";

export function createInitialCareerForm(): CareerFormState {
  return {
    full_name: "",
    career_summary: "",
    self_pr: "",
    experiences: [{ ...blankCareerExperience }],
    qualifications: [{ ...blankResumeQualification }],
  };
}

/** プロジェクト 1 件が入力空（既定の blank 構造のまま）かどうか。 */
function _isProjectEmpty(p: CareerProjectForm): boolean {
  if (p.is_current) return false;
  if (p.team.members.length !== 0 || p.phases.length !== 0) return false;
  return (
    !p.name.trim() &&
    !p.start_date.trim() &&
    !p.end_date.trim() &&
    !p.role.trim() &&
    !p.description.trim() &&
    !p.challenge.trim() &&
    !p.action.trim() &&
    !p.result.trim() &&
    !p.team.total.trim()
  );
}

/** experience 1 件が入力空（既定の blank 構造のまま）かどうかを判定する。
 *  上書き判定で使うため、ネストしたクライアント／プロジェクトも含めて検査する。
 */
function _isExperienceEmpty(e: CareerExperienceForm): boolean {
  if (e.is_current) return false;
  if (
    e.company.trim() ||
    e.business_description.trim() ||
    e.start_date.trim() ||
    e.end_date.trim() ||
    e.employee_count.trim() ||
    e.capital.trim()
  ) {
    return false;
  }
  return e.clients.every((c) => !c.name.trim() && c.projects.every(_isProjectEmpty));
}

/**
 * PDF インポート結果をフォームに反映する（上書き）。
 *
 * インポート内容を優先してフォームを上書きする。ただし PDF から値が取得できなかった
 * （imported が空の）項目については、既存の入力を消さずに維持する。
 *
 * マージルール（imported 優先）:
 * - string フィールド: imported に値があれば上書き、無ければ existing を維持
 * - experiences: imported に有効な経歴が1件でもあれば imported で置換、無ければ existing を維持
 * - qualifications: imported に有効な資格が1件でもあれば imported で置換、無ければ existing を維持
 */
export function mergeImportedResume(
  existing: CareerFormState,
  imported: CareerResumePayload,
): CareerFormState {
  // インポートデータを一旦 CareerFormState 形式に変換する
  const importedForm = mapCareerResumeToForm({
    ...imported,
    id: "",
    created_at: "",
    updated_at: "",
  });

  const full_name = importedForm.full_name.trim() ? importedForm.full_name : existing.full_name;
  const career_summary = importedForm.career_summary.trim()
    ? importedForm.career_summary
    : existing.career_summary;
  const self_pr = importedForm.self_pr.trim() ? importedForm.self_pr : existing.self_pr;

  // imported に有効な経歴が1件でもあれば丸ごと置換、無ければ既存を維持する
  const hasImportedExperiences = importedForm.experiences.some((e) => !_isExperienceEmpty(e));
  const experiences = hasImportedExperiences ? importedForm.experiences : existing.experiences;

  // imported に有効な資格が1件でもあれば丸ごと置換、無ければ既存を維持する
  const hasImportedQualifications = importedForm.qualifications.some(
    (q) => q.name.trim() || q.acquired_date.trim(),
  );
  const qualifications = hasImportedQualifications
    ? importedForm.qualifications
    : existing.qualifications;

  return { full_name, career_summary, self_pr, experiences, qualifications };
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
          clients:
            experience.clients.length > 0
              ? experience.clients.map((client) => ({
                ...client,
                projects:
                  client.projects.length > 0
                    ? client.projects.map((project) => ({
                      ...project,
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
