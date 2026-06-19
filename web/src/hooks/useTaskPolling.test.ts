import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, type Mock } from "vitest";
import { useTaskPolling } from "./useTaskPolling";

/** ポーリング間隔を短くしてテストを高速化する */
const FAST_INTERVAL = 50;

describe("useTaskPolling", () => {
  /**
   * テスト共通の renderHook + コールバック作成を集約する setup ファクトリ。
   * checkStatus は呼び出し側で挙動を組み立てる（mockResolvedValue / mockRejectedValue 等）。
   * onCompleted / onFailed は省略時は新規 vi.fn() で生成し、overrides で差し替え可能。
   */
  function setup(
    checkStatus: Mock,
    overrides: {
      onCompleted?: Mock;
      onFailed?: Mock;
      intervalMs?: number;
    } = {},
  ) {
    const onCompleted = overrides.onCompleted ?? vi.fn();
    const onFailed = overrides.onFailed ?? vi.fn();
    const hook = renderHook(() =>
      useTaskPolling({
        checkStatus,
        onCompleted,
        onFailed,
        intervalMs: overrides.intervalMs ?? FAST_INTERVAL,
      }),
    );
    return { ...hook, onCompleted, onFailed };
  }

  it("completed になったとき onCompleted が呼ばれる", async () => {
    const checkStatus = vi.fn().mockResolvedValue({ status: "completed" });
    const { result, onCompleted, onFailed } = setup(checkStatus);

    act(() => {
      result.current.startPolling();
    });

    await waitFor(() => {
      expect(onCompleted).toHaveBeenCalledOnce();
    });
    expect(onFailed).not.toHaveBeenCalled();
    expect(result.current.isPolling).toBe(false);
  });

  it("dead_letter になったとき onFailed が呼ばれる", async () => {
    const checkStatus = vi.fn().mockResolvedValue({
      status: "dead_letter",
      error_message: "分析処理がタイムアウトしました",
    });
    const { result, onCompleted, onFailed } = setup(checkStatus);

    act(() => {
      result.current.startPolling();
    });

    await waitFor(() => {
      expect(onFailed).toHaveBeenCalledWith(
        expect.objectContaining({
          code: "INTERNAL_ERROR",
          message: "分析処理がタイムアウトしました",
        }),
      );
    });
    expect(onCompleted).not.toHaveBeenCalled();
    expect(result.current.isPolling).toBe(false);
  });

  it("dead_letter で error_message がない場合デフォルトメッセージが渡される", async () => {
    const checkStatus = vi.fn().mockResolvedValue({ status: "dead_letter" });
    const { result, onFailed } = setup(checkStatus);

    act(() => {
      result.current.startPolling();
    });

    await waitFor(() => {
      expect(onFailed).toHaveBeenCalledWith(
        expect.objectContaining({
          code: "INTERNAL_ERROR",
          message: "処理に失敗しました",
        }),
      );
    });
  });

  it("pending 中はポーリングが継続し completed で停止する", async () => {
    const checkStatus = vi
      .fn()
      .mockResolvedValueOnce({ status: "pending" })
      .mockResolvedValueOnce({ status: "pending" })
      .mockResolvedValue({ status: "completed" });
    const { result, onCompleted } = setup(checkStatus);

    act(() => {
      result.current.startPolling();
    });

    await waitFor(() => {
      expect(onCompleted).toHaveBeenCalledOnce();
    });
    // 少なくとも3回呼ばれている（pending, pending, completed）
    expect(checkStatus.mock.calls.length).toBeGreaterThanOrEqual(3);
  });

  it("アンマウント時にポーリングが停止する", async () => {
    // fake timers で仮想時間を進め、実時間待ち（フレーキー要因）を排除する
    vi.useFakeTimers();
    try {
      const checkStatus = vi.fn().mockResolvedValue({ status: "pending" });
      const { result, unmount } = setup(checkStatus);

      act(() => {
        result.current.startPolling();
      });

      // マウント中は 1 インターバル進めるとポーリングが反復する（初回即時 + 次回）
      await act(async () => {
        await vi.advanceTimersByTimeAsync(FAST_INTERVAL);
      });
      const callCountWhileMounted = checkStatus.mock.calls.length;
      expect(callCountWhileMounted).toBeGreaterThanOrEqual(2);

      unmount();

      // アンマウント後は次回タイマーが破棄され、何インターバル進めても呼び出しは増えない
      await act(async () => {
        await vi.advanceTimersByTimeAsync(FAST_INTERVAL * 3);
      });
      expect(checkStatus.mock.calls.length).toBe(callCountWhileMounted);
    } finally {
      vi.useRealTimers();
    }
  });

  it("ネットワークエラー時はポーリングが継続する", async () => {
    const checkStatus = vi
      .fn()
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue({ status: "completed" });
    const { result, onCompleted } = setup(checkStatus);

    act(() => {
      result.current.startPolling();
    });

    await waitFor(() => {
      expect(onCompleted).toHaveBeenCalledOnce();
    });
    // エラー後にリトライして completed に到達
    expect(checkStatus.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
