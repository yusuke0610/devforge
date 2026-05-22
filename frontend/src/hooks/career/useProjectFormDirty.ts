import { useMemo } from "react";

import { blankCareerProject } from "../../constants";
import type { CareerProjectForm } from "../../payloadBuilders";

/** ProjectModal 内で表示する dirty マップ */
export type ProjectFormDirty = {
  /** 全体の dirty 有無（モーダルタイトル横の集約表示用） */
  any: boolean;
  /** 単純フィールドの dirty */
  fields: {
    name: boolean;
    start_date: boolean;
    end_date: boolean;
    is_current: boolean;
    role: boolean;
    description: boolean;
    challenge: boolean;
    action: boolean;
    result: boolean;
  };
  /** 体制セクションの dirty（全体人数 or メンバー配列が変化） */
  team: boolean;
  /** 技術スタックセクションの dirty（配列いずれかが変化） */
  technology_stacks: boolean;
  /** 工程セクションの dirty（phases 配列が変化） */
  phases: boolean;
};

/** 値が等しいかを判定する（プリミティブ・配列・プレーンオブジェクトを再帰比較）。 */
function isDeepEqual(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (a === null || b === null) return false;
  if (typeof a !== "object" || typeof b !== "object") return false;

  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b)) return false;
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!isDeepEqual(a[i], b[i])) return false;
    }
    return true;
  }

  const objA = a as Record<string, unknown>;
  const objB = b as Record<string, unknown>;
  const keysA = Object.keys(objA);
  const keysB = Object.keys(objB);
  if (keysA.length !== keysB.length) return false;
  for (const k of keysA) {
    if (!Object.prototype.hasOwnProperty.call(objB, k)) return false;
    if (!isDeepEqual(objA[k], objB[k])) return false;
  }
  return true;
}

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
      start_date: local.start_date !== base.start_date,
      end_date: local.end_date !== base.end_date,
      is_current: local.is_current !== base.is_current,
      role: local.role !== base.role,
      description: local.description !== base.description,
      challenge: local.challenge !== base.challenge,
      action: local.action !== base.action,
      result: local.result !== base.result,
    };

    const team = !isDeepEqual(local.team, base.team);
    const technology_stacks = !isDeepEqual(local.technology_stacks, base.technology_stacks);
    const phases = !isDeepEqual(local.phases, base.phases);

    const any =
      Object.values(fields).some(Boolean) || team || technology_stacks || phases;

    return { any, fields, team, technology_stacks, phases };
  }, [local, original]);
}
