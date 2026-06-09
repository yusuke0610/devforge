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
  CareerClientForm,
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
  /**
   * 指定 index の experience を updater で書き換える共通ヘルパ。
   * 三階層 immutable 更新の「該当 1 件だけ map で差し替える」定型をここに集約する。
   */
  const updateExperienceAt = (
    expIndex: number,
    updater: (exp: CareerExperienceForm) => CareerExperienceForm,
  ) => {
    setForm((prev) => ({
      ...prev,
      experiences: prev.experiences.map((exp, ei) => (ei === expIndex ? updater(exp) : exp)),
    }));
  };

  /**
   * 指定座標（experience → client）の client を updater で書き換える共通ヘルパ。
   * updateExperienceAt の上に client 1 件差し替えを重ねる。
   */
  const updateClientAt = (
    expIndex: number,
    clientIndex: number,
    updater: (client: CareerClientForm) => CareerClientForm,
  ) => {
    updateExperienceAt(expIndex, (exp) => ({
      ...exp,
      clients: exp.clients.map((c, ci) => (ci === clientIndex ? updater(c) : c)),
    }));
  };

  /** experience フィールド変更ハンドラ */
  const updateExperienceField = (
    index: number,
    key: CareerExperienceFieldKey,
    value: string | boolean,
  ) => {
    updateExperienceAt(index, (exp) => {
      if (key === "is_current") {
        const isCurrent = Boolean(value);
        return { ...exp, is_current: isCurrent, end_date: isCurrent ? "" : exp.end_date };
      }
      return { ...exp, [key]: value };
    });
  };

  /** client フィールド変更ハンドラ */
  const updateClientField = (
    expIndex: number,
    clientIndex: number,
    key: CareerClientFieldKey,
    value: string,
  ) => {
    updateClientAt(expIndex, clientIndex, (c) => ({ ...c, [key]: value }));
  };

  /** 「取引先なし」フラグ切り替えハンドラ */
  const updateClientHasClient = (expIndex: number, clientIndex: number, value: boolean) => {
    updateClientAt(expIndex, clientIndex, (c) => ({
      ...c,
      has_client: value,
      name: value ? c.name : "",
    }));
  };

  /** 「休暇」フラグ切り替えハンドラ */
  const updateClientIsVacation = (expIndex: number, clientIndex: number, value: boolean) => {
    updateClientAt(expIndex, clientIndex, (c) => ({ ...c, is_vacation: value }));
  };

  /** 休暇の「継続中」フラグ切り替えハンドラ（継続中なら終了年月をクリア） */
  const updateClientVacationIsCurrent = (
    expIndex: number,
    clientIndex: number,
    value: boolean,
  ) => {
    updateClientAt(expIndex, clientIndex, (c) => ({
      ...c,
      vacation_is_current: value,
      vacation_end_date: value ? "" : c.vacation_end_date,
    }));
  };

  /** 取引先追加ハンドラ */
  const addClient = (expIndex: number) => {
    updateExperienceAt(expIndex, (exp) => ({
      ...exp,
      clients: [...exp.clients, { ...blankCareerClient }],
    }));
  };

  /** 取引先削除ハンドラ（最後の 1 件は空レコードへリセット） */
  const removeClient = (expIndex: number, clientIndex: number) => {
    updateExperienceAt(expIndex, (exp) => ({
      ...exp,
      clients:
        exp.clients.length === 1
          ? [{ ...blankCareerClient }]
          : exp.clients.filter((_, ci) => ci !== clientIndex),
    }));
  };

  /** プロジェクト削除ハンドラ（最後の 1 件は空レコードへリセット） */
  const removeProject = (expIndex: number, clientIndex: number, projIndex: number) => {
    updateClientAt(expIndex, clientIndex, (c) => ({
      ...c,
      projects:
        c.projects.length === 1
          ? [{ ...blankCareerProject }]
          : c.projects.filter((_, pi) => pi !== projIndex),
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
   * 指定座標の client が現在持つプロジェクト数を返す。
   * 新規プロジェクトを末尾に追加した際の確定 index 算出に使う。
   */
  const getProjectCount = (expIndex: number, clientIndex: number): number => {
    return experiences[expIndex]?.clients[clientIndex]?.projects.length ?? 0;
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
    updateClientAt(expIndex, clientIndex, (c) =>
      projIndex === null
        ? { ...c, projects: [...c.projects, project] }
        : { ...c, projects: c.projects.map((p, pi) => (pi === projIndex ? project : p)) },
    );
  };

  return {
    updateExperienceField,
    updateClientField,
    updateClientHasClient,
    updateClientIsVacation,
    updateClientVacationIsCurrent,
    addClient,
    removeClient,
    removeProject,
    addExperience,
    removeExperience,
    getProject,
    getProjectCount,
    onProjectSave,
  };
}
