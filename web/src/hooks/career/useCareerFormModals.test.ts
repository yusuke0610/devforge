import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

import { useCareerFormModals } from "./useCareerFormModals";

describe("useCareerFormModals", () => {
  const makeDeps = () => ({
    deleteDoc: vi.fn().mockResolvedValue(undefined),
  });

  it("削除確認モーダルの開閉", () => {
    const { result } = renderHook(() => useCareerFormModals(makeDeps()));

    expect(result.current.showDeleteConfirm).toBe(false);

    act(() => {
      result.current.setShowDeleteConfirm(true);
    });
    expect(result.current.showDeleteConfirm).toBe(true);

    act(() => {
      result.current.setShowDeleteConfirm(false);
    });
    expect(result.current.showDeleteConfirm).toBe(false);
  });

  it("handleDelete: deleteDoc を呼び、モーダルを閉じる", async () => {
    const deps = makeDeps();
    const { result } = renderHook(() => useCareerFormModals(deps));

    act(() => {
      result.current.setShowDeleteConfirm(true);
    });
    expect(result.current.showDeleteConfirm).toBe(true);

    await act(async () => {
      await result.current.handleDelete();
    });
    expect(deps.deleteDoc).toHaveBeenCalledTimes(1);
    expect(result.current.showDeleteConfirm).toBe(false);
  });

  it("editingField: 自己PR / 職務要約の切り替えと閉じる", () => {
    const { result } = renderHook(() => useCareerFormModals(makeDeps()));

    expect(result.current.editingField).toBeNull();

    act(() => {
      result.current.setEditingField("self_pr");
    });
    expect(result.current.editingField).toBe("self_pr");

    act(() => {
      result.current.setEditingField("career_summary");
    });
    expect(result.current.editingField).toBe("career_summary");

    act(() => {
      result.current.setEditingField(null);
    });
    expect(result.current.editingField).toBeNull();
  });
});
