import { renderHook } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { useFocusOnMatch } from "./useFocusOnMatch";

describe("useFocusOnMatch", () => {
  it("active=true で要素が渡されるとフォーカスされる", () => {
    const { result } = renderHook(() => useFocusOnMatch<HTMLInputElement>(true));
    const input = document.createElement("input");
    document.body.appendChild(input);

    result.current(input);

    expect(document.activeElement).toBe(input);
    input.remove();
  });

  it("active=false なら要素が渡されてもフォーカスされない", () => {
    const { result } = renderHook(() => useFocusOnMatch<HTMLInputElement>(false));
    const input = document.createElement("input");
    document.body.appendChild(input);

    result.current(input);

    expect(document.activeElement).not.toBe(input);
    input.remove();
  });

  it("null が渡されても例外を投げない", () => {
    const { result } = renderHook(() => useFocusOnMatch<HTMLInputElement>(true));
    expect(() => result.current(null)).not.toThrow();
  });

  it("active が false→true に変わるとコールバックの identity が変わる（再アタッチ用）", () => {
    const { result, rerender } = renderHook(
      ({ active }: { active: boolean }) => useFocusOnMatch<HTMLInputElement>(active),
      { initialProps: { active: false } },
    );
    const first = result.current;
    rerender({ active: true });
    expect(result.current).not.toBe(first);
  });
});
