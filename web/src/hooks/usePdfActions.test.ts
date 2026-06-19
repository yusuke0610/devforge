import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { usePdfActions } from "./usePdfActions";

describe("usePdfActions", () => {
  // 各テストで使用するモック関数
  const mockDownloadPdf = vi.fn();
  const mockDownloadMarkdown = vi.fn();
  const mockGetPdfBlobUrl = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  /** onDownloadPdf を呼ぶと downloadPdf が実行され success がセットされること */
  it("onDownloadPdf を呼ぶと downloadPdf API が呼ばれ success がセットされる", async () => {
    mockDownloadPdf.mockResolvedValueOnce(undefined);

    const { result } = renderHook(() =>
      usePdfActions({
        downloadPdf: mockDownloadPdf,
        downloadMarkdown: mockDownloadMarkdown,
        getPdfBlobUrl: mockGetPdfBlobUrl,
      }),
    );

    await act(async () => {
      await result.current.onDownloadPdf("doc-123", "ダウンロード完了");
    });

    expect(mockDownloadPdf).toHaveBeenCalledWith("doc-123");
    expect(result.current.success).toBe("ダウンロード完了");
    expect(result.current.error).toBeNull();
  });

  /** onPreviewPdf を呼ぶと getPdfBlobUrl が実行され previewUrl がセットされること */
  it("onPreviewPdf を呼ぶと getPdfBlobUrl API が呼ばれ previewUrl がセットされる", async () => {
    const mockUrl = "blob:http://localhost/test-blob";
    mockGetPdfBlobUrl.mockResolvedValueOnce(mockUrl);

    const { result } = renderHook(() =>
      usePdfActions({
        downloadPdf: mockDownloadPdf,
        downloadMarkdown: mockDownloadMarkdown,
        getPdfBlobUrl: mockGetPdfBlobUrl,
      }),
    );

    await act(async () => {
      await result.current.onPreviewPdf("doc-456");
    });

    expect(mockGetPdfBlobUrl).toHaveBeenCalledWith("doc-456");
    expect(result.current.previewUrl).toBe(mockUrl);
    expect(result.current.error).toBeNull();
  });

  /** closePreview を呼ぶと URL.revokeObjectURL が呼ばれ previewUrl が null になること */
  it("closePreview を呼ぶと URL.revokeObjectURL が呼ばれ previewUrl が null になる", async () => {
    const mockUrl = "blob:http://localhost/revoke-test";
    mockGetPdfBlobUrl.mockResolvedValueOnce(mockUrl);
    const revokeObjectURLSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});

    const { result } = renderHook(() =>
      usePdfActions({
        downloadPdf: mockDownloadPdf,
        downloadMarkdown: mockDownloadMarkdown,
        getPdfBlobUrl: mockGetPdfBlobUrl,
      }),
    );

    await act(async () => {
      await result.current.onPreviewPdf("doc-789");
    });

    expect(result.current.previewUrl).toBe(mockUrl);

    act(() => {
      result.current.closePreview();
    });

    expect(revokeObjectURLSpy).toHaveBeenCalledWith(mockUrl);
    expect(result.current.previewUrl).toBeNull();

    revokeObjectURLSpy.mockRestore();
  });

  /** clearMessages を呼ぶと error と success がクリアされること */
  it("clearMessages を呼ぶと error と success がクリアされる", async () => {
    mockDownloadPdf.mockRejectedValueOnce(new Error("ダウンロードに失敗しました"));

    const { result } = renderHook(() =>
      usePdfActions({
        downloadPdf: mockDownloadPdf,
        downloadMarkdown: mockDownloadMarkdown,
        getPdfBlobUrl: mockGetPdfBlobUrl,
      }),
    );

    await act(async () => {
      await result.current.onDownloadPdf("doc-err", "完了");
    });

    expect(result.current.error).toBe("ダウンロードに失敗しました");

    act(() => {
      result.current.clearMessages();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.success).toBeNull();
  });
});
