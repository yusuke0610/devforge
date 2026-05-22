import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useResumeImport } from "../useResumeImport";

// API モジュールをモック化
vi.mock("../../../api/resumeImports", () => ({
  startResumeImport: vi.fn(),
  getResumeImportStatus: vi.fn(),
  getResumeImportResult: vi.fn(),
}));

import {
  getResumeImportStatus,
  startResumeImport,
} from "../../../api/resumeImports";

const mockStart = startResumeImport as ReturnType<typeof vi.fn>;
const mockStatus = getResumeImportStatus as ReturnType<typeof vi.fn>;

function makePdf(size = 1024): File {
  return new File([new Uint8Array(size)], "resume.pdf", { type: "application/pdf" });
}

describe("useResumeImport", () => {
  it("初期状態は idle", () => {
    const { result } = renderHook(() => useResumeImport());
    expect(result.current.phase).toBe("idle");
    expect(result.current.parsedData).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("PDF 以外のファイルは error になる", async () => {
    const { result } = renderHook(() => useResumeImport());
    const nonPdf = new File(["text"], "file.txt", { type: "text/plain" });

    await act(async () => {
      await result.current.start(nonPdf);
    });

    expect(result.current.phase).toBe("error");
    expect(result.current.error?.code).toBe("RESUME_IMPORT_INVALID");
  });

  it("10MB 超過ファイルは error になる", async () => {
    const { result } = renderHook(() => useResumeImport());
    const oversized = new File([new Uint8Array(11 * 1024 * 1024)], "big.pdf", {
      type: "application/pdf",
    });

    await act(async () => {
      await result.current.start(oversized);
    });

    expect(result.current.phase).toBe("error");
    expect(result.current.error?.code).toBe("RESUME_IMPORT_INVALID");
  });

  it("正常アップロード → polling フェーズに遷移する", async () => {
    mockStart.mockResolvedValue({ import_id: "test-import-id" });
    mockStatus.mockResolvedValue({ status: "pending" });

    const { result } = renderHook(() => useResumeImport());

    await act(async () => {
      await result.current.start(makePdf());
    });

    await waitFor(() => {
      expect(result.current.phase).toBe("polling");
    });
  });

  it("reset で idle に戻る", async () => {
    mockStart.mockResolvedValue({ import_id: "test-import-id" });
    mockStatus.mockResolvedValue({ status: "pending" });

    const { result } = renderHook(() => useResumeImport());

    await act(async () => {
      await result.current.start(makePdf());
    });

    act(() => {
      result.current.reset();
    });

    expect(result.current.phase).toBe("idle");
    expect(result.current.parsedData).toBeNull();
    expect(result.current.error).toBeNull();
  });
});
