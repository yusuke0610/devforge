import { renderHook, act } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { useProjectModalForm } from "./useProjectModalForm";
import type { CareerProjectForm } from "../../payloadBuilders";

const sampleProject: CareerProjectForm = {
  name: "テスト",
  start_date: "2024-01",
  end_date: "2024-12",
  is_current: false,
  role: "Backend",
  challenge: "",
  action: "",
  result: "",
  team: { total: "5", members: [{ role: "SE", count: "3" }] },
  technology_stacks: [{ category: "language", name: "Python" }],
  phases: ["設計"],
};

describe("useProjectModalForm", () => {
  it("project=null で初期化すると空の state が返る", () => {
    const { result } = renderHook(() => useProjectModalForm(null));
    expect(result.current.local.name).toBe("");
    expect(result.current.local.is_current).toBe(false);
    expect(result.current.local.technology_stacks).toHaveLength(1);
    expect(result.current.local.team.members).toHaveLength(0);
  });

  it("既存 project は structuredClone され元データを変更しない", () => {
    const { result } = renderHook(() => useProjectModalForm(sampleProject));
    act(() => result.current.updateField("name", "差し替え"));
    expect(result.current.local.name).toBe("差し替え");
    // 元データは破壊されない
    expect(sampleProject.name).toBe("テスト");
  });

  it("is_current=true に切り替えると end_date が空にリセットされる", () => {
    const { result } = renderHook(() => useProjectModalForm(sampleProject));
    act(() => result.current.updateField("is_current", true));
    expect(result.current.local.is_current).toBe(true);
    expect(result.current.local.end_date).toBe("");
  });

  it("技術スタックのカテゴリを変えると name が空にリセットされる", () => {
    const { result } = renderHook(() => useProjectModalForm(sampleProject));
    act(() => result.current.updateTechStack(0, "category", "framework"));
    expect(result.current.local.technology_stacks[0]).toEqual({
      category: "framework",
      name: "",
    });
  });

  it("技術スタックの追加/削除が動作する", () => {
    const { result } = renderHook(() => useProjectModalForm(sampleProject));
    act(() => result.current.addTechStack());
    expect(result.current.local.technology_stacks).toHaveLength(2);
    act(() => result.current.removeTechStack(0));
    expect(result.current.local.technology_stacks).toHaveLength(1);
  });

  it("技術スタックを 1 件のみ残して削除すると空チップが再生成される", () => {
    const { result } = renderHook(() =>
      useProjectModalForm({
        ...sampleProject,
        technology_stacks: [{ category: "language", name: "Go" }],
      }),
    );
    act(() => result.current.removeTechStack(0));
    expect(result.current.local.technology_stacks).toHaveLength(1);
    expect(result.current.local.technology_stacks[0]).toEqual({ category: "language", name: "" });
  });

  it("チームメンバーの追加・削除・更新が動作する", () => {
    const { result } = renderHook(() => useProjectModalForm(sampleProject));
    act(() => result.current.addTeamMember());
    expect(result.current.local.team.members).toHaveLength(2);
    act(() => result.current.updateTeamMember(1, "role", "PM"));
    expect(result.current.local.team.members[1]).toEqual({ role: "PM", count: "" });
    act(() => result.current.removeTeamMember(0));
    expect(result.current.local.team.members).toHaveLength(1);
  });

  it("phase をトグルできる（追加→削除）", () => {
    const { result } = renderHook(() => useProjectModalForm(sampleProject));
    act(() => result.current.togglePhase("実装"));
    expect(result.current.local.phases).toContain("実装");
    act(() => result.current.togglePhase("設計"));
    expect(result.current.local.phases).not.toContain("設計");
  });

  it("開始日 > 終了日 のとき dateError が生成される", () => {
    const { result } = renderHook(() =>
      useProjectModalForm({ ...sampleProject, start_date: "2024-12", end_date: "2024-01" }),
    );
    expect(result.current.dateError).not.toBeNull();
  });

  it("is_current=true なら dateError は発生しない", () => {
    const { result } = renderHook(() =>
      useProjectModalForm({
        ...sampleProject,
        start_date: "2024-12",
        end_date: "2024-01",
        is_current: true,
      }),
    );
    expect(result.current.dateError).toBeNull();
  });
});
