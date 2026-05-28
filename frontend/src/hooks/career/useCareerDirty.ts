import { useMemo } from "react";

import type {
  CareerClientForm,
  CareerExperienceForm,
  CareerFormState,
  CareerProjectForm,
} from "../../payloadBuilders";
import type { ResumeQualification } from "../../types";
import { isDeepEqual } from "../../utils/deepEqual";

/** プロジェクト単位の dirty 情報。`any` は配下含めた未保存有無。 */
export type ProjectDirty = {
  any: boolean;
};

/** クライアント単位の dirty 情報。 */
export type ClientDirty = {
  /** クライアント自身またはその配下プロジェクトのいずれかが未保存 */
  any: boolean;
  /** クライアント直下のフィールド（name / has_client）が未保存 */
  self: boolean;
  projects: ProjectDirty[];
};

/** 職務経歴1件分の dirty 情報。 */
export type ExperienceDirty = {
  /** 経歴自身または配下クライアント／プロジェクトのいずれかが未保存 */
  any: boolean;
  /** 経歴直下のフィールド（company 等）が未保存 */
  self: boolean;
  fields: {
    company: boolean;
    business_description: boolean;
    start_date: boolean;
    end_date: boolean;
    is_current: boolean;
    employee_count: boolean;
    capital: boolean;
    capital_unit: boolean;
    is_it_company: boolean;
    description: boolean;
  };
  clients: ClientDirty[];
};

/** 資格1件分の dirty 情報。 */
export type QualificationDirty = {
  /** 資格行のいずれかのフィールドが未保存 */
  self: boolean;
  fields: {
    name: boolean;
    acquired_date: boolean;
  };
};

/** 職務経歴書全体の dirty マップ。 */
export type CareerDirtyMap = {
  /** 全体で何か未保存があるか（保存ボタン横用） */
  any: boolean;
  full_name: boolean;
  career_summary: boolean;
  self_pr: boolean;
  experiences: ExperienceDirty[];
  /** 「職務経歴」h2 用集約 */
  experiencesAny: boolean;
  qualifications: QualificationDirty[];
  /** 「資格」h2 用集約 */
  qualificationsAny: boolean;
};

/** dirty なしの経歴 1 件分のテンプレート。配下クライアントとプロジェクトは form の shape を踏襲する。 */
function buildCleanExperience(
  experience: { clients: { projects: unknown[] }[] },
): ExperienceDirty {
  return {
    any: false,
    self: false,
    fields: {
      company: false,
      business_description: false,
      start_date: false,
      end_date: false,
      is_current: false,
      employee_count: false,
      capital: false,
      capital_unit: false,
      is_it_company: false,
      description: false,
    },
    clients: experience.clients.map((c) => ({
      any: false,
      self: false,
      projects: c.projects.map(() => ({ any: false })),
    })),
  };
}

const emptyQualification: QualificationDirty = {
  self: false,
  fields: { name: false, acquired_date: false },
};

/** baseline が null のとき（未ロード）に返す「全 false」のマップ。 */
function buildClean(form: CareerFormState): CareerDirtyMap {
  return {
    any: false,
    full_name: false,
    career_summary: false,
    self_pr: false,
    experiences: form.experiences.map((exp) => buildCleanExperience(exp)),
    experiencesAny: false,
    qualifications: form.qualifications.map(() => emptyQualification),
    qualificationsAny: false,
  };
}

function diffProject(
  current: CareerProjectForm,
  base: CareerProjectForm | undefined,
): ProjectDirty {
  if (!base) return { any: true };
  return { any: !isDeepEqual(current, base) };
}

function diffClient(
  current: CareerClientForm,
  base: CareerClientForm | undefined,
): ClientDirty {
  if (!base) {
    // 追加されたクライアント丸ごと dirty。配下プロジェクトもすべて dirty 扱いにする。
    return {
      any: true,
      self: true,
      projects: current.projects.map(() => ({ any: true })),
    };
  }
  const selfFieldsDirty =
    current.name !== base.name ||
    current.has_client !== base.has_client ||
    current.is_vacation !== base.is_vacation ||
    current.vacation_start_date !== base.vacation_start_date ||
    current.vacation_end_date !== base.vacation_end_date ||
    current.vacation_is_current !== base.vacation_is_current ||
    current.vacation_description !== base.vacation_description;
  const projects = current.projects.map((p, i) => diffProject(p, base.projects[i]));
  const removedProjects = current.projects.length !== base.projects.length;
  const any =
    selfFieldsDirty ||
    removedProjects ||
    projects.some((p) => p.any);
  return { any, self: selfFieldsDirty, projects };
}

function diffExperience(
  current: CareerExperienceForm,
  base: CareerExperienceForm | undefined,
): ExperienceDirty {
  if (!base) {
    return {
      any: true,
      self: true,
      fields: {
        company: true,
        business_description: true,
        start_date: true,
        end_date: true,
        is_current: true,
        employee_count: true,
        capital: true,
        capital_unit: true,
        is_it_company: true,
        description: true,
      },
      clients: current.clients.map((c) => ({
        any: true,
        self: true,
        projects: c.projects.map(() => ({ any: true })),
      })),
    };
  }
  const fields: ExperienceDirty["fields"] = {
    company: current.company !== base.company,
    business_description: current.business_description !== base.business_description,
    start_date: current.start_date !== base.start_date,
    end_date: current.end_date !== base.end_date,
    is_current: current.is_current !== base.is_current,
    employee_count: current.employee_count !== base.employee_count,
    capital: current.capital !== base.capital,
    capital_unit: current.capital_unit !== base.capital_unit,
    is_it_company: current.is_it_company !== base.is_it_company,
    description: current.description !== base.description,
  };
  const self = Object.values(fields).some(Boolean);
  const clients = current.clients.map((c, i) => diffClient(c, base.clients[i]));
  const removedClients = current.clients.length !== base.clients.length;
  const any = self || removedClients || clients.some((c) => c.any);
  return { any, self, fields, clients };
}

function diffQualification(
  current: ResumeQualification,
  base: ResumeQualification | undefined,
): QualificationDirty {
  if (!base) {
    return { self: true, fields: { name: true, acquired_date: true } };
  }
  const fields = {
    name: current.name !== base.name,
    acquired_date: current.acquired_date !== base.acquired_date,
  };
  return { self: fields.name || fields.acquired_date, fields };
}

/**
 * 職務経歴書フォームの dirty マップを算出するフック。
 * baseline が null（未ロード）のときはすべて false を返し、誤検出を避ける。
 */
export function useCareerDirty(
  form: CareerFormState,
  baseline: CareerFormState | null,
): CareerDirtyMap {
  return useMemo(() => {
    if (!baseline) return buildClean(form);

    const full_name = form.full_name !== baseline.full_name;
    const career_summary = form.career_summary !== baseline.career_summary;
    const self_pr = form.self_pr !== baseline.self_pr;

    const experiences = form.experiences.map((exp, i) =>
      diffExperience(exp, baseline.experiences[i]),
    );
    const removedExperiences =
      form.experiences.length !== baseline.experiences.length;
    const experiencesAny = removedExperiences || experiences.some((e) => e.any);

    const qualifications = form.qualifications.map((q, i) =>
      diffQualification(q, baseline.qualifications[i]),
    );
    const removedQualifications =
      form.qualifications.length !== baseline.qualifications.length;
    const qualificationsAny =
      removedQualifications || qualifications.some((q) => q.self);

    const any =
      full_name || career_summary || self_pr || experiencesAny || qualificationsAny;

    return {
      any,
      full_name,
      career_summary,
      self_pr,
      experiences,
      experiencesAny,
      qualifications,
      qualificationsAny,
    };
  }, [form, baseline]);
}
