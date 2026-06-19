import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useProjectModalState } from "./useProjectModalState";
import type { CareerProjectForm } from "../../payloadBuilders";

const dummyProject: CareerProjectForm = {
  name: "テストプロジェクト",
  periods: [{ start_date: "2024-01", end_date: "2024-12", is_current: false }],
  role: "エンジニア",
  description: "",
  team: { total: "", members: [] },
  technology_stacks: [],
  phases: [],
};

describe("useProjectModalState", () => {
  /** 既存プロジェクト編集: onSave が同じ index で呼ばれ、モーダルは閉じない（即時反映のため） */
  it("既存プロジェクトは handleProjectSave で onSave を呼ぶがモーダルは閉じない", () => {
    const getProject = vi.fn().mockReturnValue(dummyProject);
    const onSave = vi.fn();
    const getProjectCount = vi.fn().mockReturnValue(3);
    const { result } = renderHook(() =>
      useProjectModalState(getProject, onSave, getProjectCount),
    );

    act(() => {
      result.current.setModalTarget({ expIndex: 1, clientIndex: 2, projIndex: 3 });
    });

    act(() => {
      result.current.handleProjectSave(dummyProject);
    });

    expect(onSave).toHaveBeenCalledWith(1, 2, 3, dummyProject);
    // 即時反映なので閉じない。閉じるのは × / オーバーレイ（closeModal）だけ。
    expect(result.current.modalTarget).toEqual({ expIndex: 1, clientIndex: 2, projIndex: 3 });
  });

  /** 新規プロジェクト: 初回反映で末尾に append し、確定 index を modalTarget へ反映する */
  it("新規プロジェクトは初回反映で append し projIndex を確定する", () => {
    const getProject = vi.fn().mockReturnValue(null);
    const onSave = vi.fn();
    // 該当 client は既に 2 件持っている → 新規は index 2 に確定する。
    const getProjectCount = vi.fn().mockReturnValue(2);
    const { result } = renderHook(() =>
      useProjectModalState(getProject, onSave, getProjectCount),
    );

    act(() => {
      result.current.setModalTarget({ expIndex: 0, clientIndex: 0, projIndex: null });
    });

    act(() => {
      result.current.handleProjectSave(dummyProject);
    });

    // 初回は append（projIndex=null）で onSave。
    expect(onSave).toHaveBeenCalledWith(0, 0, null, dummyProject);
    expect(getProjectCount).toHaveBeenCalledWith(0, 0);
    // 以後は更新パスになるよう projIndex が確定する。
    expect(result.current.modalTarget).toEqual({ expIndex: 0, clientIndex: 0, projIndex: 2 });

    // 2 回目以降は確定 index で更新（再 append しない）。
    act(() => {
      result.current.handleProjectSave(dummyProject);
    });
    expect(onSave).toHaveBeenLastCalledWith(0, 0, 2, dummyProject);
  });

  /** closeModal でモーダルが閉じる */
  it("closeModal で modalTarget が null になる", () => {
    const getProject = vi.fn().mockReturnValue(dummyProject);
    const onSave = vi.fn();
    const getProjectCount = vi.fn().mockReturnValue(0);
    const { result } = renderHook(() =>
      useProjectModalState(getProject, onSave, getProjectCount),
    );

    act(() => {
      result.current.setModalTarget({ expIndex: 1, clientIndex: 2, projIndex: 3 });
    });
    act(() => {
      result.current.closeModal();
    });

    expect(result.current.modalTarget).toBeNull();
  });
});
