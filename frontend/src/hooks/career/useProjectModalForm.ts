import { useState } from "react";

import {
  blankCareerProject,
  blankCareerProjectPeriod,
  blankCareerTechnologyStack,
  blankTeamMember,
} from "../../constants";
import type { CareerProjectFieldKey, CareerProjectPeriodFieldKey } from "../../formTypes";
import {
  validatePeriods,
  type CareerProjectForm,
  type CareerProjectPeriodForm,
} from "../../payloadBuilders";
import type { CareerTechnologyStack, CareerTechnologyStackCategory } from "../../types";

/**
 * 編集対象が無い（新規追加）場合の初期プロジェクトを生成する。
 * 既存プロジェクトを編集する場合は structuredClone で副作用を切る。
 *
 * 初期値の唯一の SSoT は `constants.ts:blankCareerProject`。フィールド追加・改名は
 * そちらで行えば本フックも自動追従する。
 */
export function initProject(project: CareerProjectForm | null): CareerProjectForm {
  if (project) {
    return structuredClone(project);
  }
  return structuredClone(blankCareerProject);
}

/**
 * プロジェクト編集モーダルの state と nested update ハンドラを提供するフック。
 * ProjectModal の責務を JSX に絞るために、データ操作ロジックを切り出している。
 */
export function useProjectModalForm(project: CareerProjectForm | null) {
  const [local, setLocal] = useState<CareerProjectForm>(() => initProject(project));

  const updateField = (key: CareerProjectFieldKey, value: string) => {
    setLocal((prev) => ({ ...prev, [key]: value }));
  };

  const addPeriod = () => {
    setLocal((prev) => ({
      ...prev,
      periods: [...prev.periods, { ...blankCareerProjectPeriod }],
    }));
  };

  const removePeriod = (periodIndex: number) => {
    setLocal((prev) => ({
      ...prev,
      periods:
        prev.periods.length === 1
          ? [{ ...blankCareerProjectPeriod }]
          : prev.periods.filter((_, i) => i !== periodIndex),
    }));
  };

  const updatePeriodField = (
    periodIndex: number,
    key: CareerProjectPeriodFieldKey,
    value: string | boolean,
  ) => {
    setLocal((prev) => ({
      ...prev,
      periods: prev.periods.map((p, i): CareerProjectPeriodForm => {
        if (i !== periodIndex) return p;
        if (key === "is_current") {
          const isCurrent = Boolean(value);
          return { ...p, is_current: isCurrent, end_date: isCurrent ? "" : p.end_date };
        }
        return { ...p, [key]: value };
      }),
    }));
  };

  const updateTechStack = (
    stackIndex: number,
    key: keyof CareerTechnologyStack,
    value: string,
  ) => {
    setLocal((prev) => ({
      ...prev,
      technology_stacks: prev.technology_stacks.map((stack, si) => {
        if (si !== stackIndex) return stack;
        if (key === "category") {
          return { ...stack, category: value as CareerTechnologyStackCategory, name: "" };
        }
        return { ...stack, name: value };
      }),
    }));
  };

  const addTechStack = () => {
    setLocal((prev) => ({
      ...prev,
      technology_stacks: [...prev.technology_stacks, { ...blankCareerTechnologyStack }],
    }));
  };

  const removeTechStack = (stackIndex: number) => {
    setLocal((prev) => ({
      ...prev,
      technology_stacks:
        prev.technology_stacks.length === 1
          ? [{ ...blankCareerTechnologyStack }]
          : prev.technology_stacks.filter((_, si) => si !== stackIndex),
    }));
  };

  const updateTeamTotal = (value: string) => {
    setLocal((prev) => ({ ...prev, team: { ...prev.team, total: value } }));
  };

  const addTeamMember = () => {
    setLocal((prev) => ({
      ...prev,
      team: { ...prev.team, members: [...prev.team.members, { ...blankTeamMember }] },
    }));
  };

  const removeTeamMember = (memberIndex: number) => {
    setLocal((prev) => ({
      ...prev,
      team: {
        ...prev.team,
        members: prev.team.members.filter((_, mi) => mi !== memberIndex),
      },
    }));
  };

  const updateTeamMember = (memberIndex: number, key: "role" | "count", value: string) => {
    setLocal((prev) => ({
      ...prev,
      team: {
        ...prev.team,
        members: prev.team.members.map((m, mi) =>
          mi === memberIndex ? { ...m, [key]: value } : m,
        ),
      },
    }));
  };

  const togglePhase = (phase: string) => {
    setLocal((prev) => {
      const phases = prev.phases.includes(phase)
        ? prev.phases.filter((p) => p !== phase)
        : [...prev.phases, phase];
      return { ...prev, phases };
    });
  };

  const dateError = validatePeriods(local.periods);

  return {
    local,
    dateError,
    updateField,
    addPeriod,
    removePeriod,
    updatePeriodField,
    updateTechStack,
    addTechStack,
    removeTechStack,
    updateTeamTotal,
    addTeamMember,
    removeTeamMember,
    updateTeamMember,
    togglePhase,
  };
}
