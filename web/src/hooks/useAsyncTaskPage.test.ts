import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  useAsyncTaskPage,
  type UseAsyncTaskPageOptions,
} from "./useAsyncTaskPage";

describe("useAsyncTaskPage", () => {
  const mockLoadCache = vi.fn();
  const mockCheckStatus = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  /**
   * 4 箇所の renderHook + props 標準セット (loadCache / checkStatus) のコピペを集約する setup ファクトリ。
   * `overrides` で fetchProgress 等の追加 props を渡せる。
   */
  type TestResult = { id: string };
  function setup(
    overrides: Partial<UseAsyncTaskPageOptions<TestResult>> = {},
  ) {
    return renderHook(() =>
      useAsyncTaskPage<TestResult>({
        loadCache: mockLoadCache,
        checkStatus: mockCheckStatus,
        ...overrides,
      }),
    );
  }

  /** 初回マウント時にキャッシュが存在する場合、result フェーズに遷移すること */
  it("キャッシュが存在する場合 result フェーズに遷移する", async () => {
    mockLoadCache.mockResolvedValue({ result: { id: "test-result" } });
    mockCheckStatus.mockResolvedValue({ status: "completed" });

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.phase).toBe("result");
    });

    expect(result.current.result).toEqual({ id: "test-result" });
  });

  /** 初回マウント時にキャッシュが存在しない場合、input フェーズに遷移すること */
  it("キャッシュが存在しない場合 input フェーズに遷移する", async () => {
    mockLoadCache.mockResolvedValue({ result: null });
    mockCheckStatus.mockResolvedValue({ status: "idle" });

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.phase).toBe("input");
    });

    expect(result.current.result).toBeNull();
  });

  /** 初回マウント時に status が retrying の場合、polling フェーズに遷移すること */
  it("status が retrying の場合 polling フェーズに遷移する", async () => {
    mockLoadCache.mockResolvedValue({ result: null, status: "retrying" });
    mockCheckStatus.mockResolvedValue({ status: "retrying" });

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.phase).toBe("polling");
    });
  });

  /** 初回マウント時に status が pending の場合、polling フェーズに遷移すること */
  it("status が pending の場合 polling フェーズに遷移する", async () => {
    mockLoadCache.mockResolvedValue({ result: null, status: "pending" });
    // ポーリングが止まらないよう pending を返し続ける
    mockCheckStatus.mockResolvedValue({ status: "pending" });

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.phase).toBe("polling");
    });
  });

  /** ポーリングで status: "dead_letter" を返した場合、input フェーズに戻ること */
  it("ポーリングで status が dead_letter の場合 input フェーズに戻る", async () => {
    // 初回は pending → polling フェーズに遷移
    mockLoadCache.mockResolvedValue({ result: null, status: "pending" });
    // ポーリング中に dead_letter を返す
    mockCheckStatus.mockResolvedValue({
      status: "dead_letter",
      error_message: "分析に失敗しました",
    });

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.phase).toBe("input");
    });

    expect(result.current.error).toEqual(
      expect.objectContaining({
        code: "INTERNAL_ERROR",
        message: "分析に失敗しました",
      }),
    );
  });

  /** transitionToPolling を呼ぶと polling フェーズに遷移すること */
  it("transitionToPolling を呼ぶと polling フェーズに遷移する", async () => {
    mockLoadCache.mockResolvedValue({ result: null });
    mockCheckStatus.mockResolvedValue({ status: "pending" });

    const { result } = setup();

    // input フェーズになるまで待つ
    await waitFor(() => {
      expect(result.current.phase).toBe("input");
    });

    act(() => {
      result.current.transitionToPolling();
    });

    expect(result.current.phase).toBe("polling");
  });

  /** backToInput を呼ぶと input フェーズに戻り result がリセットされること */
  it("backToInput を呼ぶと input フェーズに戻り result がリセットされる", async () => {
    mockLoadCache.mockResolvedValue({ result: { id: "existing" } });
    mockCheckStatus.mockResolvedValue({ status: "completed" });

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.phase).toBe("result");
    });

    act(() => {
      result.current.backToInput();
    });

    expect(result.current.phase).toBe("input");
    expect(result.current.result).toBeNull();
  });

  /**
   * fetchProgress が reject しても polling は継続し、progress は null のまま。
   * Redis 障害等の進捗取得失敗で hook 全体が壊れないことを守る。
   */
  it("fetchProgress が reject しても polling フェーズが維持される", async () => {
    mockLoadCache.mockResolvedValue({ result: null, status: "pending" });
    mockCheckStatus.mockResolvedValue({ status: "pending" });
    const mockFetchProgress = vi.fn().mockRejectedValue(new Error("Redis down"));

    const { result } = setup({ fetchProgress: mockFetchProgress });

    await waitFor(() => {
      expect(result.current.phase).toBe("polling");
    });

    await waitFor(() => {
      expect(mockFetchProgress).toHaveBeenCalled();
    });

    // fetchProgress が reject しても polling 本体は続行し、progress は null のまま
    expect(result.current.phase).toBe("polling");
    expect(result.current.progress).toBeNull();
  });

  /** loadCache でエラーが発生した場合、input フェーズに遷移すること */
  it("loadCache でエラーが発生した場合 input フェーズに遷移する", async () => {
    mockLoadCache.mockRejectedValue(new Error("ネットワークエラー"));
    mockCheckStatus.mockResolvedValue({ status: "idle" });

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.phase).toBe("input");
    });
  });
});
