import { act, renderHook, waitFor } from "@testing-library/react";
import { configureStore } from "@reduxjs/toolkit";
import React from "react";
import { Provider } from "react-redux";
import { describe, expect, it, vi } from "vitest";

import resumeImportReducer, {
  type ResumeImportState,
} from "../../../store/resumeImportSlice";
import { useResumeImport } from "../useResumeImport";

// API モジュールをモック化
vi.mock("../../../api/resumeImports", () => ({
  startResumeImport: vi.fn(),
  getResumeImportStatus: vi.fn(),
  getResumeImportResult: vi.fn(),
}));

import {
  getResumeImportResult,
  startResumeImport,
} from "../../../api/resumeImports";

const mockStart = startResumeImport as ReturnType<typeof vi.fn>;
const mockResult = getResumeImportResult as ReturnType<typeof vi.fn>;

/** Redux Provider 付きの renderHook ラッパーを生成する */
function createWrapper() {
  const store = configureStore({
    reducer: { resumeImport: resumeImportReducer },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(Provider, { store, children });
  };
}

function makePdf(size = 1024): File {
  return new File([new Uint8Array(size)], "resume.pdf", { type: "application/pdf" });
}

describe("useResumeImport", () => {
  it("初期状態は idle", () => {
    const { result } = renderHook(() => useResumeImport(), {
      wrapper: createWrapper(),
    });
    expect(result.current.phase).toBe("idle");
    expect(result.current.parsedData).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("PDF 以外のファイルは error になる", async () => {
    const { result } = renderHook(() => useResumeImport(), {
      wrapper: createWrapper(),
    });
    const nonPdf = new File(["text"], "file.txt", { type: "text/plain" });

    await act(async () => {
      await result.current.start(nonPdf);
    });

    expect(result.current.phase).toBe("error");
    expect(result.current.error?.code).toBe("RESUME_IMPORT_INVALID");
  });

  it("10MB 超過ファイルは error になる", async () => {
    const { result } = renderHook(() => useResumeImport(), {
      wrapper: createWrapper(),
    });
    const oversized = new File([new Uint8Array(11 * 1024 * 1024)], "big.pdf", {
      type: "application/pdf",
    });

    await act(async () => {
      await result.current.start(oversized);
    });

    expect(result.current.phase).toBe("error");
    expect(result.current.error?.code).toBe("RESUME_IMPORT_INVALID");
  });

  it("正常アップロード → polling フェーズに遷移し importId が Redux に格納される", async () => {
    mockStart.mockResolvedValue({ import_id: "test-import-id" });

    const { result } = renderHook(() => useResumeImport(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.start(makePdf());
    });

    await waitFor(() => {
      expect(result.current.phase).toBe("polling");
    });
  });

  it("reset で idle に戻る", async () => {
    mockStart.mockResolvedValue({ import_id: "test-import-id" });

    const { result } = renderHook(() => useResumeImport(), {
      wrapper: createWrapper(),
    });

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

  it("phase が ready に遷移した際に解析結果を API から取得する", async () => {
    // 初期に importId/phase をセットした store を作る
    const preloaded: ResumeImportState = {
      importId: "ready-import-id",
      phase: "ready",
      error: null,
      progress: null,
    };
    const store = configureStore({
      reducer: { resumeImport: resumeImportReducer },
      preloadedState: { resumeImport: preloaded },
    });
    mockResult.mockResolvedValue({
      result: { full_name: "山田 太郎", career_summary: "", experiences: [], qualifications: [], self_pr: "" },
      is_resume: true,
      judge_reason: "判定OK",
    });

    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(Provider, { store, children });

    const { result } = renderHook(() => useResumeImport(), { wrapper });

    await waitFor(() => {
      expect(result.current.parsedData?.result.full_name).toBe("山田 太郎");
    });
    expect(mockResult).toHaveBeenCalledWith("ready-import-id");
  });
});
