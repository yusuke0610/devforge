import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { ApiError } from "../utils/appError";
import { useResumeDraftPdf } from "./useResumeDraftPdf";

// API モジュールをモックし、フックの状態遷移だけを検証する
vi.mock("../api/agent", () => ({
  generateResumeDraftPdfBlobUrl: vi.fn(),
}));

import { generateResumeDraftPdfBlobUrl } from "../api/agent";

const mockGenerate = vi.mocked(generateResumeDraftPdfBlobUrl);

describe("useResumeDraftPdf", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  /** 成功時: previewUrl がセットされ、選択モデルで API が呼ばれること */
  it("generate 成功で previewUrl がセットされる", async () => {
    mockGenerate.mockResolvedValueOnce("blob:http://localhost/draft-pdf");

    const { result } = renderHook(() => useResumeDraftPdf("haiku"));
    await act(async () => {
      await result.current.generate();
    });

    expect(mockGenerate).toHaveBeenCalledWith("haiku");
    expect(result.current.previewUrl).toBe("blob:http://localhost/draft-pdf");
    expect(result.current.error).toBeNull();
    expect(result.current.generating).toBe(false);
  });

  /** 生成中: generating が true になり、完了で false に戻ること */
  it("generate 中は generating が true になる", async () => {
    let resolveFetch: (url: string) => void = () => {};
    mockGenerate.mockImplementationOnce(
      () => new Promise<string>((resolve) => (resolveFetch = resolve)),
    );

    const { result } = renderHook(() => useResumeDraftPdf("haiku"));
    let pending: Promise<void>;
    act(() => {
      pending = result.current.generate();
    });
    expect(result.current.generating).toBe(true);

    await act(async () => {
      resolveFetch("blob:http://localhost/x");
      await pending;
    });
    expect(result.current.generating).toBe(false);
  });

  /** 失敗時: ApiError の message / action が AppErrorState に保持されること */
  it("generate 失敗で backend のエラー内容が error にセットされる", async () => {
    mockGenerate.mockRejectedValueOnce(
      new ApiError({
        code: "VALIDATION_ERROR",
        message: "連携データがありません",
        action: "GitHub 連携を実行してください",
      }),
    );

    const { result } = renderHook(() => useResumeDraftPdf("haiku"));
    await act(async () => {
      await result.current.generate();
    });

    expect(result.current.previewUrl).toBeNull();
    expect(result.current.error?.message).toBe("連携データがありません");
    expect(result.current.error?.action).toBe("GitHub 連携を実行してください");
  });

  /** closePreview: Blob URL が解放され previewUrl が null に戻ること */
  it("closePreview で URL.revokeObjectURL が呼ばれ previewUrl が null になる", async () => {
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    mockGenerate.mockResolvedValueOnce("blob:http://localhost/to-revoke");

    const { result } = renderHook(() => useResumeDraftPdf("haiku"));
    await act(async () => {
      await result.current.generate();
    });
    act(() => {
      result.current.closePreview();
    });

    expect(revokeSpy).toHaveBeenCalledWith("blob:http://localhost/to-revoke");
    expect(result.current.previewUrl).toBeNull();
    revokeSpy.mockRestore();
  });

  /** 再生成: 旧 previewUrl が revoke されてから新 URL に差し替わること（Blob リーク防止） */
  it("generate を再実行すると旧 Blob URL が revoke される", async () => {
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    mockGenerate
      .mockResolvedValueOnce("blob:http://localhost/first")
      .mockResolvedValueOnce("blob:http://localhost/second");

    const { result } = renderHook(() => useResumeDraftPdf("haiku"));
    await act(async () => {
      await result.current.generate();
    });
    await act(async () => {
      await result.current.generate();
    });

    expect(revokeSpy).toHaveBeenCalledWith("blob:http://localhost/first");
    expect(result.current.previewUrl).toBe("blob:http://localhost/second");
    revokeSpy.mockRestore();
  });

  /** アンマウント: プレビュー表示中に画面離脱しても Blob URL が解放されること */
  it("アンマウント時に残っている Blob URL が revoke される", async () => {
    const revokeSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    mockGenerate.mockResolvedValueOnce("blob:http://localhost/on-unmount");

    const { result, unmount } = renderHook(() => useResumeDraftPdf("haiku"));
    await act(async () => {
      await result.current.generate();
    });
    unmount();

    expect(revokeSpy).toHaveBeenCalledWith("blob:http://localhost/on-unmount");
    revokeSpy.mockRestore();
  });
});
