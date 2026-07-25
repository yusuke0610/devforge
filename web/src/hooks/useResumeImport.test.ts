import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api";
import { useResumeImport } from "./useResumeImport";

vi.mock("../api/agent", () => ({
  importResumePdf: vi.fn(),
}));

import { importResumePdf } from "../api/agent";

const mockImport = vi.mocked(importResumePdf);

function _pdfFile(): File {
  return new File([new Uint8Array([0x25, 0x50, 0x44, 0x46])], "resume.pdf", {
    type: "application/pdf",
  });
}

describe("useResumeImport", () => {
  beforeEach(() => {
    mockImport.mockReset();
  });

  it("初期状態は importing=false・error=null", () => {
    const { result } = renderHook(() => useResumeImport());
    expect(result.current.importing).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("成功時は抽出 payload を返し error は立たない", async () => {
    const payload = {
      full_name: "山田 太郎",
      career_summary: "要約",
      self_pr: "PR",
      experiences: [],
    };
    mockImport.mockResolvedValueOnce(payload);

    const { result } = renderHook(() => useResumeImport());
    let returned: unknown;
    await act(async () => {
      returned = await result.current.importPdf(_pdfFile());
    });

    expect(returned).toEqual(payload);
    expect(result.current.error).toBeNull();
    expect(result.current.importing).toBe(false);
    expect(mockImport).toHaveBeenCalledTimes(1);
  });

  it("失敗時は null を返し error に AppErrorState を立てる", async () => {
    mockImport.mockRejectedValueOnce(
      new ApiError({ code: "VALIDATION_ERROR", message: "テキストを含む PDF のみ対応しています。" }),
    );

    const { result } = renderHook(() => useResumeImport());
    let returned: unknown = "unset";
    await act(async () => {
      returned = await result.current.importPdf(_pdfFile());
    });

    expect(returned).toBeNull();
    expect(result.current.error).not.toBeNull();
    expect(result.current.error?.message).toBe("テキストを含む PDF のみ対応しています。");
    expect(result.current.importing).toBe(false);
  });

  it("clearError で error をクリアできる", async () => {
    mockImport.mockRejectedValueOnce(new ApiError({ code: "INTERNAL_ERROR", message: "失敗" }));
    const { result } = renderHook(() => useResumeImport());
    await act(async () => {
      await result.current.importPdf(_pdfFile());
    });
    expect(result.current.error).not.toBeNull();
    act(() => result.current.clearError());
    expect(result.current.error).toBeNull();
  });
});
