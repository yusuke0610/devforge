import type { Dispatch, SetStateAction } from "react";

import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
} from "../../constants";
import type {
  CareerClientFieldKey,
  CareerExperienceFieldKey,
} from "../../formTypes";
import type {
  CareerExperienceForm,
  CareerFormState,
  CareerProjectForm,
} from "../../payloadBuilders";

/**
 * 職務経歴フォームの experience / client / project 三階層に対する
 * nested update ハンドラをまとめて提供するカスタムフック。
 * CareerExperienceSection の責務をデータ操作のみに絞るために分離。
 */
export function useCareerExperienceMutators(
  experiences: CareerExperienceForm[],
  setForm: Dispatch<SetStateAction<CareerFormState>>,
) {
  /** experience フィールド変更ハンドラ */
  const updateExperienceField = (
    index: number,
    key: CareerExperienceFieldKey,
    value: string | boolean,
  ) => {
    setForm((prev) => ({
      ...prev,
      experiences: prev.experiences.map((exp, i) => {
        if (i !== index) return exp;
        if (key === "is_current") {
          const isCurrent = Boolean(value);
          return { ...exp, is_current: isCurrent, end_date: isCurrent ? "" : exp.end_date };
        }
        return { ...exp, [key]: value };
      }),
    }));
  };

  /** client フィールド変更ハンドラ */
  const updateClientField = (
    expIndex: number,
    clientIndex: number,
    key: CareerClientFieldKey,
    value: string,
  ) => {
    setForm((prev) => ({
      ...prev,
      experiences: prev.experiences.map((exp, ei) => {
        if (ei !== expIndex) return exp;
        return {
          ...exp,
          clients: exp.clients.map((c, ci) =>
            ci === clientIndex ? { ...c, [key]: value } : c,
          ),
        };
      }),
    }));
  };

  /** 「取引先なし」フラグ切り替えハンドラ */
  const updateClientHasClient = (expIndex: number, clientIndex: number, value: boolean) => {
    setForm((prev) => ({
      ...prev,
      experiences: prev.experiences.map((exp, ei) => {
        if (ei !== expIndex) return exp;
        return {
          ...exp,
          clients: exp.clients.map((c, ci) =>
            ci === clientIndex ? { ...c, has_client: value, name: value ? c.name : "" } : c,
          ),
        };
      }),
    }));
  };

  /** 取引先追加ハンドラ */
  const addClient = (expIndex: number) => {
    setForm((prev) => ({
      ...prev,
      experiences: prev.experiences.map((exp, ei) =>
        ei === expIndex
          ? { ...exp, clients: [...exp.clients, { ...blankCareerClient }] }
          : exp,
      ),
    }));
  };

  /** 取引先削除ハンドラ */
  const removeClient = (expIndex: number, clientIndex: number) => {
    setForm((prev) => ({
      ...prev,
      experiences: prev.experiences.map((exp, ei) => {
        if (ei !== expIndex) return exp;
        return {
          ...exp,
          clients:
            exp.clients.length === 1
              ? [{ ...blankCareerClient }]
              : exp.clients.filter((_, ci) => ci !== clientIndex),
        };
      }),
    }));
  };

  /** プロジェクト削除ハンドラ */
  const removeProject = (expIndex: number, clientIndex: number, projIndex: number) => {
    setForm((prev) => ({
      ...prev,
      experiences: prev.experiences.map((exp, ei) => {
        if (ei !== expIndex) return exp;
        return {
          ...exp,
          clients: exp.clients.map((c, ci) => {
            if (ci !== clientIndex) return c;
            return {
              ...c,
              projects:
                c.projects.length === 1
                  ? [{ ...blankCareerProject }]
                  : c.projects.filter((_, pi) => pi !== projIndex),
            };
          }),
        };
      }),
    }));
  };

  /** 職務経歴追加ハンドラ */
  const addExperience = () => {
    setForm((prev) => ({
      ...prev,
      experiences: [...prev.experiences, { ...blankCareerExperience }],
    }));
  };

  /** 職務経歴削除ハンドラ */
  const removeExperience = (index: number) => {
    setForm((prev) => ({
      ...prev,
      experiences:
        prev.experiences.length === 1
          ? [{ ...blankCareerExperience }]
          : prev.experiences.filter((_, i) => i !== index),
    }));
  };

  /**
   * form の experiences から指定座標のプロジェクトを取得する。
   * useProjectModalState に渡すコールバック用。
   */
  const getProject = (
    expIndex: number,
    clientIndex: number,
    projIndex: number,
  ): CareerProjectForm | null => {
    return experiences[expIndex]?.clients[clientIndex]?.projects[projIndex] ?? null;
  };

  /**
   * モーダルで保存されたプロジェクトをフォームに反映する。
   * useProjectModalState に渡すコールバック用。
   */
  const onProjectSave = (
    expIndex: number,
    clientIndex: number,
    projIndex: number | null,
    project: CareerProjectForm,
  ) => {
    setForm((prev) => ({
      ...prev,
      experiences: prev.experiences.map((exp, ei) => {
        if (ei !== expIndex) return exp;
        return {
          ...exp,
          clients: exp.clients.map((c, ci) => {
            if (ci !== clientIndex) return c;
            if (projIndex === null) {
              return { ...c, projects: [...c.projects, project] };
            }
            return {
              ...c,
              projects: c.projects.map((p, pi) => (pi === projIndex ? project : p)),
            };
          }),
        };
      }),
    }));
  };

  return {
    updateExperienceField,
    updateClientField,
    updateClientHasClient,
    addClient,
    removeClient,
    removeProject,
    addExperience,
    removeExperience,
    getProject,
    onProjectSave,
  };
}
