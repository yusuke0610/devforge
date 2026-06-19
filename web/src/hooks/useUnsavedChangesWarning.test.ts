import { renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { useUnsavedChangesWarning } from "./useUnsavedChangesWarning";

/** beforeunload を dispatch し、ハンドラが preventDefault したか（defaultPrevented）を返す。 */
function dispatchBeforeUnload(): boolean {
  const event = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(event);
  return event.defaultPrevented;
}

describe("useUnsavedChangesWarning", () => {
  it("when=true の間は beforeunload を抑止する（離脱確認を出す）", () => {
    renderHook(() => useUnsavedChangesWarning(true));
    expect(dispatchBeforeUnload()).toBe(true);
  });

  it("when=false なら beforeunload を抑止しない（リスナ未登録）", () => {
    renderHook(() => useUnsavedChangesWarning(false));
    expect(dispatchBeforeUnload()).toBe(false);
  });

  it("アンマウント後はリスナを解除する", () => {
    const { unmount } = renderHook(() => useUnsavedChangesWarning(true));
    unmount();
    expect(dispatchBeforeUnload()).toBe(false);
  });

  it("when が true→false に変わるとリスナを解除する", () => {
    const { rerender } = renderHook(
      ({ when }: { when: boolean }) => useUnsavedChangesWarning(when),
      { initialProps: { when: true } },
    );
    expect(dispatchBeforeUnload()).toBe(true);
    rerender({ when: false });
    expect(dispatchBeforeUnload()).toBe(false);
  });
});
