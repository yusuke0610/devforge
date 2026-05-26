import { renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { blankCareerProject, blankCareerTechnologyStack } from "../../constants";
import type { CareerProjectForm } from "../../payloadBuilders";
import { useProjectFormDirty } from "./useProjectFormDirty";

/** 標準的なプロジェクトデータを作るヘルパ */
function buildProject(overrides: Partial<CareerProjectForm> = {}): CareerProjectForm {
  return {
    name: "プロジェクトX",
    start_date: "2021-04",
    end_date: "2022-03",
    is_current: false,
    role: "Eng",
    challenge: "課題",
    action: "行動",
    result: "成果",
    team: { total: "5", members: [{ role: "PM", count: "1" }] },
    technology_stacks: [{ category: "language", name: "TypeScript" }],
    phases: ["要件定義", "開発"],
    ...overrides,
  };
}

describe("useProjectFormDirty", () => {
  it("original と local が同一なら dirty なし", () => {
    const original = buildProject();
    const local = buildProject();
    const { result } = renderHook(() => useProjectFormDirty(local, original));
    expect(result.current.any).toBe(false);
    expect(result.current.fields.name).toBe(false);
    expect(result.current.team).toBe(false);
    expect(result.current.technology_stacks).toBe(false);
    expect(result.current.phases).toBe(false);
  });

  it("プロジェクト名を変更すると fields.name と any が true", () => {
    const original = buildProject();
    const local = buildProject({ name: "プロジェクトY" });
    const { result } = renderHook(() => useProjectFormDirty(local, original));
    expect(result.current.fields.name).toBe(true);
    expect(result.current.any).toBe(true);
    // 他は false
    expect(result.current.fields.role).toBe(false);
    expect(result.current.team).toBe(false);
  });

  it("体制（team.total）を変更すると team が true", () => {
    const original = buildProject();
    const local = buildProject({ team: { total: "10", members: original.team.members } });
    const { result } = renderHook(() => useProjectFormDirty(local, original));
    expect(result.current.team).toBe(true);
    expect(result.current.any).toBe(true);
  });

  it("技術スタックを追加すると technology_stacks が true", () => {
    const original = buildProject();
    const local = buildProject({
      technology_stacks: [...original.technology_stacks, { ...blankCareerTechnologyStack }],
    });
    const { result } = renderHook(() => useProjectFormDirty(local, original));
    expect(result.current.technology_stacks).toBe(true);
    expect(result.current.any).toBe(true);
  });

  it("工程（phases）を変更すると phases が true", () => {
    const original = buildProject();
    const local = buildProject({ phases: ["要件定義"] });
    const { result } = renderHook(() => useProjectFormDirty(local, original));
    expect(result.current.phases).toBe(true);
    expect(result.current.any).toBe(true);
  });

  it("新規追加（original=null）の場合は blankCareerProject と比較し、入力すると dirty", () => {
    const local = buildProject(); // 入力済み
    const { result } = renderHook(() => useProjectFormDirty(local, null));
    expect(result.current.any).toBe(true);
    expect(result.current.fields.name).toBe(true);
    expect(result.current.fields.role).toBe(true);
  });

  it("新規追加（original=null）で blankCareerProject と同一の local は dirty なし", () => {
    const local = structuredClone(blankCareerProject);
    const { result } = renderHook(() => useProjectFormDirty(local, null));
    expect(result.current.any).toBe(false);
  });
});
