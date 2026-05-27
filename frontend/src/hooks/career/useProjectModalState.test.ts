import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { useProjectModalState } from "./useProjectModalState";
import type { CareerProjectForm } from "../../payloadBuilders";

const dummyProject: CareerProjectForm = {
  name: "テストプロジェクト",
  start_date: "2024-01",
  end_date: "2024-12",
  is_current: false,
  role: "エンジニア",
  description: "",
  team: { total: "", members: [] },
  technology_stacks: [],
  phases: [],
};

describe("useProjectModalState", () => {
  /** handleProjectSave を呼ぶと onSave が実行され modalTarget が null になること */
  it("handleProjectSave を呼ぶと onSave が呼ばれ closeModal が実行される", () => {
    const getProject = vi.fn().mockReturnValue(dummyProject);
    const onSave = vi.fn();
    const { result } = renderHook(() => useProjectModalState(getProject, onSave));

    act(() => {
      result.current.setModalTarget({ expIndex: 1, clientIndex: 2, projIndex: 3 });
    });

    act(() => {
      result.current.handleProjectSave(dummyProject);
    });

    expect(onSave).toHaveBeenCalledWith(1, 2, 3, dummyProject);
    expect(result.current.modalTarget).toBeNull();
  });
});
