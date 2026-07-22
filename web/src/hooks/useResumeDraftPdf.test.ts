import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiError } from "../utils/appError";
import { useResumeDraftPdf } from "./useResumeDraftPdf";

// API モジュールをモックし、フックの状態遷移（enqueue → ポーリング → 取得）だけを検証する
vi.mock("../api/agent", () => ({
  startResumeDraft: vi.fn(),
  getResumeDraftStatus: vi.fn(),
  fetchResumeDraftPdfBlobUrl: vi.fn(),
}));

import {
  startResumeDraft,
  getResumeDraftStatus,
  fetchResumeDraftPdfBlobUrl,
} from "../api/agent";

const mockStart = vi.mocked(startResumeDraft);
const mockStatus = vi.mocked(getResumeDraftStatus);
const mockFetch = vi.mocked(fetchResumeDraftPdfBlobUrl);

describe("useResumeDraftPdf", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 既定: マウント時・ポーリングとも「完了」を返す（マウント復帰は発火しない）
    mockStatus.mockResolvedValue({ status: "completed" });
    mockStart.mockResolvedValue({ status: "pending" });
  });

  /** 成功時: enqueue → ポーリング完了 → PDF 取得で previewUrl がセットされ、選択モデルで enqueue される */
  it("generate 成功で previewUrl がセットされる", async () => {
    mockFetch.mockResolvedValueOnce("blob:http://localhost/draft-pdf");

    const { result } = renderHook(() => useResumeDraftPdf());
    await act(async () => {
      await result.current.generate();
    });

    await waitFor(() =>
      expect(result.current.previewUrl).toBe("blob:http://localhost/draft-pdf"),
    );
    expect(mockStart).toHaveBeenCalledWith();
    expect(result.current.error).toBeNull();
    expect(result.current.generating).toBe(false);
  });

  /** 生成中: generating が true になり、PDF 取得完了で false に戻ること */
  it("generate 中は generating が true になる", async () => {
    let resolveFetch: (url: string) => void = () => {};
    mockFetch.mockImplementationOnce(
      () => new Promise<string>((resolve) => (resolveFetch = resolve)),
    );

    const { result } = renderHook(() => useResumeDraftPdf());
    await act(async () => {
      await result.current.generate();
    });
    // enqueue → ポーリング完了 → PDF 取得が pending の間は generating が true
    await waitFor(() => expect(result.current.generating).toBe(true));

    await act(async () => {
      resolveFetch("blob:http://localhost/x");
    });
    await waitFor(() => expect(result.current.generating).toBe(false));
  });

  /** enqueue 失敗（409 連携データ不足など）: backend の message / action が error に保持される */
  it("enqueue 失敗で backend のエラー内容が error にセットされる", async () => {
    mockStart.mockRejectedValueOnce(
      new ApiError({
        code: "VALIDATION_ERROR",
        message: "連携データがありません",
        action: "GitHub 連携を実行してください",
      }),
    );

    const { result } = renderHook(() => useResumeDraftPdf());
    await act(async () => {
      await result.current.generate();
    });

    expect(result.current.previewUrl).toBeNull();
    expect(result.current.error?.message).toBe("連携データがありません");
    expect(result.current.error?.action).toBe("GitHub 連携を実行してください");
    expect(result.current.generating).toBe(false);
  });

  /** タスク失敗（dead_letter）: ポーリングが失敗を検知して error にセットされる */
  it("生成タスクが dead_letter になると error にセットされる", async () => {
    mockStatus.mockResolvedValueOnce({ status: "completed" }); // マウント復帰は発火させない
    mockStatus.mockResolvedValue({
      status: "dead_letter",
      error_message: "AI の応答取得に失敗しました。",
      error_code: "AGENT_LLM_ERROR",
    });

    const { result } = renderHook(() => useResumeDraftPdf());
    await act(async () => {
      await result.current.generate();
    });

    await waitFor(() =>
      expect(result.current.error?.message).toBe("AI の応答取得に失敗しました。"),
    );
    expect(result.current.previewUrl).toBeNull();
    expect(result.current.generating).toBe(false);
  });

  /** マウント復帰: 進行中タスクを検知するとポーリングを再開し、完了で previewUrl がセットされる */
  it("マウント時に進行中タスクがあればポーリングを再開して復帰する", async () => {
    mockStatus.mockResolvedValueOnce({ status: "processing" }); // マウント時: 進行中
    mockStatus.mockResolvedValue({ status: "completed" }); // 以降のポーリング
    mockFetch.mockResolvedValueOnce("blob:http://localhost/resumed");

    const { result } = renderHook(() => useResumeDraftPdf());

    await waitFor(() =>
      expect(result.current.previewUrl).toBe("blob:http://localhost/resumed"),
    );
    // マウント復帰では enqueue は行わない
    expect(mockStart).not.toHaveBeenCalled();
  });

  /** closePreview: Blob URL が解放され previewUrl が null に戻ること */
  it("closePreview で URL.revokeObjectURL が呼ばれ previewUrl が null になる", async () => {
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    mockFetch.mockResolvedValueOnce("blob:http://localhost/to-revoke");

    const { result } = renderHook(() => useResumeDraftPdf());
    await act(async () => {
      await result.current.generate();
    });
    await waitFor(() => expect(result.current.previewUrl).not.toBeNull());
    act(() => {
      result.current.closePreview();
    });

    expect(revokeSpy).toHaveBeenCalledWith("blob:http://localhost/to-revoke");
    expect(result.current.previewUrl).toBeNull();
    revokeSpy.mockRestore();
  });

  /** アンマウント: プレビュー表示中に画面離脱しても Blob URL が解放されること */
  it("アンマウント時に残っている Blob URL が revoke される", async () => {
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    mockFetch.mockResolvedValueOnce("blob:http://localhost/on-unmount");

    const { result, unmount } = renderHook(() => useResumeDraftPdf());
    await act(async () => {
      await result.current.generate();
    });
    await waitFor(() => expect(result.current.previewUrl).not.toBeNull());
    unmount();

    expect(revokeSpy).toHaveBeenCalledWith("blob:http://localhost/on-unmount");
    revokeSpy.mockRestore();
  });
});
