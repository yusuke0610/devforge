import { useMemo } from "react";

import { blankCareerProject } from "../../constants";
import type { CareerProjectForm } from "../../payloadBuilders";
import { isDeepEqual } from "../../utils/deepEqual";

/** ProjectModal 内で表示する dirty マップ */
export type ProjectFormDirty = {
  /** 全体の dirty 有無（モーダルタイトル横の集約表示用） */
  any: boolean;
  /** 単純フィールドの dirty */
  fields: {
    name: boolean;
    role: boolean;
    description: boolean;
  };
  /** 期間セクションの dirty（periods 配列が変化） */
  periods: boolean;
  /** 体制セクションの dirty（全体人数 or メンバー配列が変化） */
  team: boolean;
  /** 技術スタックセクションの dirty（配列いずれかが変化） */
  technology_stacks: boolean;
  /** 工程セクションの dirty（phases 配列が変化） */
  phases: boolean;
};

/**
 * ProjectModal の編集中フォーム (local) と元データ (original) を比較し、
 * フィールド単位の未保存マップを返すフック。
 *
 * - 既存プロジェクト編集: original = 親フォームから渡された現在のプロジェクト
 * - 新規プロジェクト追加: original = null → blankCareerProject と比較し、入力した項目を dirty として扱う
 */
export function useProjectFormDirty(
  local: CareerProjectForm,
  original: CareerProjectForm | null,
): ProjectFormDirty {
  return useMemo(() => {
    const base = original ?? blankCareerProject;

    const fields = {
      name: local.name !== base.name,
      role: local.role !== base.role,
      description: local.description !== base.description,
    };

    const periods = !isDeepEqual(local.periods, base.periods);
    const team = !isDeepEqual(local.team, base.team);
    const technology_stacks = !isDeepEqual(local.technology_stacks, base.technology_stacks);
    const phases = !isDeepEqual(local.phases, base.phases);

    const any = Object.values(fields).some(Boolean) || periods || team || technology_stacks || phases;

    return { any, fields, periods, team, technology_stacks, phases };
  }, [local, original]);
}
