import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useAsyncResource } from "./useAsyncResource";

const FALLBACK = "取得に失敗しました";

describe("useAsyncResource", () => {
  it("enabled=true で取得し data に反映する", async () => {
    const fetcher = vi.fn().mockResolvedValue(42);

    const { result } = renderHook(() =>
      useAsyncResource(fetcher, { enabled: true, initialData: 0, fallbackMessage: FALLBACK }),
    );

    await waitFor(() => {
      expect(result.current.data).toBe(42);
    });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("enabled=false の間は取得せず initialData のまま", () => {
    const fetcher = vi.fn().mockResolvedValue(42);

    const { result } = renderHook(() =>
      useAsyncResource(fetcher, { enabled: false, initialData: 0, fallbackMessage: FALLBACK }),
    );

    expect(fetcher).not.toHaveBeenCalled();
    expect(result.current.data).toBe(0);
    // 取得が走らないので最初から loading=false
    expect(result.current.loading).toBe(false);
  });

  it("Error の reject では message を、それ以外では fallback を error に入れる", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("固有エラー"));
    const { result, rerender } = renderHook(
      (props: { f: () => Promise<number> }) =>
        useAsyncResource(props.f, { enabled: true, initialData: 0, fallbackMessage: FALLBACK }),
      { initialProps: { f: fetcher } },
    );

    await waitFor(() => {
      expect(result.current.error).toBe("固有エラー");
    });
    expect(result.current.loading).toBe(false);

    const stringRejector = vi.fn().mockRejectedValue("文字列例外");
    rerender({ f: stringRejector });
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.error).toBe(FALLBACK);
  });

  it("古い refresh 応答は新しい応答を上書きしない（seq ガード）", async () => {
    let resolveStale: (v: number) => void = () => {};
    const stalePending = new Promise<number>((resolve) => {
      resolveStale = resolve;
    });
    // enabled=false で自動取得を抑止し、手動 refresh の順序だけを検証する
    const fetcher = vi
      .fn<() => Promise<number>>()
      .mockReturnValueOnce(stalePending) // seq=1（保留）
      .mockResolvedValueOnce(730); // seq=2（先に解決）

    const { result } = renderHook(() =>
      useAsyncResource(fetcher, { enabled: false, initialData: 0, fallbackMessage: FALLBACK }),
    );

    await act(async () => {
      void result.current.refresh(); // seq=1
      await result.current.refresh(); // seq=2 → 730
    });
    expect(result.current.data).toBe(730);

    // 後から古い応答が解決しても最新（730）を保つ
    await act(async () => {
      resolveStale(9_999);
      await stalePending;
    });
    expect(result.current.data).toBe(730);
  });

  it("Error でも message が空文字なら fallback を使う", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error(""));
    const { result } = renderHook(() =>
      useAsyncResource(fetcher, { enabled: true, initialData: 0, fallbackMessage: FALLBACK }),
    );

    await waitFor(() => {
      expect(result.current.error).toBe(FALLBACK);
    });
  });

  it("enabled が true→false に変わると進行中の応答は反映されない", async () => {
    let resolvePending: (v: number) => void = () => {};
    const pending = new Promise<number>((resolve) => {
      resolvePending = resolve;
    });
    const fetcher = vi.fn().mockReturnValue(pending);
    const { result, rerender } = renderHook(
      (props: { enabled: boolean }) =>
        useAsyncResource(fetcher, {
          enabled: props.enabled,
          initialData: 0,
          fallbackMessage: FALLBACK,
        }),
      { initialProps: { enabled: true } },
    );
    // enabled=true で取得が走り pending（loading=true）
    expect(result.current.loading).toBe(true);

    // 無効化で進行中リクエストを stale 化し loading も解除する
    rerender({ enabled: false });
    expect(result.current.loading).toBe(false);

    // 後から解決しても data は initialData のまま（契約: 無効中は state を更新しない）
    await act(async () => {
      resolvePending(999);
      await pending;
    });
    expect(result.current.data).toBe(0);
  });

  it("enabled が false→true に変わると取得が走る", async () => {
    const fetcher = vi.fn().mockResolvedValue(7);
    const { result, rerender } = renderHook(
      (props: { enabled: boolean }) =>
        useAsyncResource(fetcher, {
          enabled: props.enabled,
          initialData: 0,
          fallbackMessage: FALLBACK,
        }),
      { initialProps: { enabled: false } },
    );

    expect(fetcher).not.toHaveBeenCalled();

    rerender({ enabled: true });
    await waitFor(() => {
      expect(result.current.data).toBe(7);
    });
  });
});
