import type { MouseEvent as ReactMouseEvent, RefObject } from "react";

import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { usePdfPanelLayout } from "./usePdfPanelLayout";

/** getBoundingClientRect を固定したコンテナ要素を作る（jsdom は既定で 0 を返すため）。 */
function makeContainerRef(right: number, width: number): RefObject<HTMLElement | null> {
  const el = document.createElement("div");
  el.getBoundingClientRect = () =>
    ({
      right,
      width,
      left: right - width,
      top: 0,
      bottom: 0,
      height: 0,
      x: right - width,
      y: 0,
      toJSON: () => ({}),
    }) as DOMRect;
  return { current: el };
}

function mouse(type: string, clientX: number): MouseEvent {
  return new MouseEvent(type, { clientX, bubbles: true });
}

const noopMouseEvent = { preventDefault: () => {} } as unknown as ReactMouseEvent;

describe("usePdfPanelLayout", () => {
  afterEach(() => {
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  });

  it("初期幅を返し、toggleMaximize で最大化を反転する", () => {
    const ref = makeContainerRef(1000, 900);
    const { result } = renderHook(() =>
      usePdfPanelLayout(ref, { initialWidth: 360, minWidth: 280, minFormWidth: 360 }),
    );

    expect(result.current.width).toBe(360);
    expect(result.current.maximized).toBe(false);

    act(() => result.current.toggleMaximize());
    expect(result.current.maximized).toBe(true);

    act(() => result.current.toggleMaximize());
    expect(result.current.maximized).toBe(false);
  });

  it("ドラッグで幅が変わり、最小/最大でクランプされる", () => {
    const ref = makeContainerRef(1000, 900);
    const { result } = renderHook(() =>
      usePdfPanelLayout(ref, { initialWidth: 360, minWidth: 280, minFormWidth: 360 }),
    );

    act(() => result.current.startResize(noopMouseEvent));

    // 幅 = right - clientX = 1000 - 550 = 450（max=900-360-38=502 内）
    act(() => window.dispatchEvent(mouse("mousemove", 550)));
    expect(result.current.width).toBe(450);

    // 左へ行き過ぎ → 最大 502（= width - minFormWidth - reservedGap）にクランプ
    act(() => window.dispatchEvent(mouse("mousemove", 100)));
    expect(result.current.width).toBe(502);

    // 右へ行き過ぎ → 最小 280 にクランプ
    act(() => window.dispatchEvent(mouse("mousemove", 900)));
    expect(result.current.width).toBe(280);
  });

  it("reservedGap を増やすと最大幅がその分だけ狭くなる", () => {
    const ref = makeContainerRef(1000, 900);
    const { result } = renderHook(() =>
      usePdfPanelLayout(ref, { minWidth: 280, minFormWidth: 360, reservedGap: 100 }),
    );

    act(() => result.current.startResize(noopMouseEvent));
    // 左端までドラッグ → max = width - minFormWidth - reservedGap = 900 - 360 - 100 = 440
    act(() => window.dispatchEvent(mouse("mousemove", 0)));
    expect(result.current.width).toBe(440);
  });

  it("mouseup 後の mousemove は幅に影響しない", () => {
    const ref = makeContainerRef(1000, 900);
    const { result } = renderHook(() =>
      usePdfPanelLayout(ref, { initialWidth: 360, minWidth: 280, minFormWidth: 360 }),
    );

    act(() => result.current.startResize(noopMouseEvent));
    act(() => window.dispatchEvent(mouse("mousemove", 550)));
    expect(result.current.width).toBe(450);

    act(() => window.dispatchEvent(mouse("mouseup", 0)));
    act(() => window.dispatchEvent(mouse("mousemove", 700)));
    expect(result.current.width).toBe(450);
  });
});
