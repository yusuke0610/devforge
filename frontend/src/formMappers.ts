import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
  blankCareerTechnologyStack,
  blankResumeQualification,
} from "./constants";
import type { CareerFormState, CareerExperienceForm } from "./payloadBuilders";
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

/** experiences が初期 blank 1件のみかどうかを判定する。 */
function _isBlankExperiences(experiences: CareerExperienceForm[]): boolean {
  if (experiences.length !== 1) return false;
  const e = experiences[0];
  return (
    !e.company.trim() &&
    !e.business_description.trim() &&
    !e.start_date.trim()
  );
}

/**
 * PDF インポート結果をフォームにマージする（非破壊オーバーレイ）。
 *
 * マージルール:
 * - string フィールド: existing が空文字なら imported で埋める
 * - experiences: existing が初期 blank 1件のみなら imported で置換、それ以外は imported を追記
 * - qualifications: existing が初期 blank 1件のみなら imported で置換、それ以外は imported を追記
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

  const full_name = existing.full_name.trim() ? existing.full_name : importedForm.full_name;
  const career_summary = existing.career_summary.trim()
    ? existing.career_summary
    : importedForm.career_summary;
  const self_pr = existing.self_pr.trim() ? existing.self_pr : importedForm.self_pr;

  let experiences: CareerExperienceForm[];
  if (importedForm.experiences.length === 0 || importedForm.experiences.every((e) => !e.company.trim())) {
    experiences = existing.experiences;
  } else if (_isBlankExperiences(existing.experiences)) {
    experiences = importedForm.experiences;
  } else {
    experiences = [...existing.experiences, ...importedForm.experiences];
  }

  const isBlankQualifications =
    existing.qualifications.length === 1 && !existing.qualifications[0].name.trim();
  let qualifications;
  if (importedForm.qualifications.length === 0) {
    qualifications = existing.qualifications;
  } else if (isBlankQualifications) {
    qualifications = importedForm.qualifications;
  } else {
    qualifications = [...existing.qualifications, ...importedForm.qualifications];
  }

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
          end_date: experience.end_date ?? "",
          clients:
            experience.clients.length > 0
              ? experience.clients.map((client) => ({
                ...client,
                projects:
                  client.projects.length > 0
                    ? client.projects.map((project) => ({
                      ...project,
                      end_date: project.end_date ?? "",
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
