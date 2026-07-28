import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useCareerExportActions } from "./useCareerExportActions";

vi.mock("../../api", () => ({
  downloadCareerResumePdf: vi.fn(),
  downloadCareerResumeMarkdown: vi.fn(),
  getCareerResumePdfBlobUrl: vi.fn(),
}));

describe("useCareerExportActions", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let api: Record<string, any>;

  beforeEach(async () => {
    vi.clearAllMocks();
    api = await import("../../api");
    api.downloadCareerResumePdf.mockResolvedValue(undefined);
    api.downloadCareerResumeMarkdown.mockResolvedValue(undefined);
    api.getCareerResumePdfBlobUrl.mockResolvedValue("blob:http://localhost/preview");
  });

  describe("未ログイン時はログイン導線へ迂回する", () => {
    it("handlePreview は requestLogin を呼び API を呼ばない", () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: false,
          resumeId: "resume-1",
          formLocked: false,
          requestLogin,
        }),
      );

      act(() => {
        result.current.handlePreview();
      });

      expect(requestLogin).toHaveBeenCalledTimes(1);
      expect(api.getCareerResumePdfBlobUrl).not.toHaveBeenCalled();
    });

    it("handleDownloadPdf は requestLogin を呼び API を呼ばない", () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: false,
          resumeId: "resume-1",
          formLocked: false,
          requestLogin,
        }),
      );

      act(() => {
        result.current.handleDownloadPdf();
      });

      expect(requestLogin).toHaveBeenCalledTimes(1);
      expect(api.downloadCareerResumePdf).not.toHaveBeenCalled();
    });

    it("handleDownloadMarkdown は requestLogin を呼び API を呼ばない", () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: false,
          resumeId: "resume-1",
          formLocked: false,
          requestLogin,
        }),
      );

      act(() => {
        result.current.handleDownloadMarkdown();
      });

      expect(requestLogin).toHaveBeenCalledTimes(1);
      expect(api.downloadCareerResumeMarkdown).not.toHaveBeenCalled();
    });
  });

  describe("resumeId が null の場合は何もしない（ログイン済み）", () => {
    it("handlePreview は API を呼ばず requestLogin も呼ばない", () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: null,
          formLocked: false,
          requestLogin,
        }),
      );

      act(() => {
        result.current.handlePreview();
      });

      expect(requestLogin).not.toHaveBeenCalled();
      expect(api.getCareerResumePdfBlobUrl).not.toHaveBeenCalled();
    });

    it("handleDownloadPdf は API を呼ばず requestLogin も呼ばない", () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: null,
          formLocked: false,
          requestLogin,
        }),
      );

      act(() => {
        result.current.handleDownloadPdf();
      });

      expect(requestLogin).not.toHaveBeenCalled();
      expect(api.downloadCareerResumePdf).not.toHaveBeenCalled();
    });

    it("handleDownloadMarkdown は API を呼ばず requestLogin も呼ばない", () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: null,
          formLocked: false,
          requestLogin,
        }),
      );

      act(() => {
        result.current.handleDownloadMarkdown();
      });

      expect(requestLogin).not.toHaveBeenCalled();
      expect(api.downloadCareerResumeMarkdown).not.toHaveBeenCalled();
    });
  });

  describe("ログイン済み・resumeId ありの場合は API を実行する", () => {
    it("handlePreview は getCareerResumePdfBlobUrl を resumeId 付きで呼ぶ", async () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: "resume-1",
          formLocked: false,
          requestLogin,
        }),
      );

      await act(async () => {
        result.current.handlePreview();
      });

      expect(requestLogin).not.toHaveBeenCalled();
      expect(api.getCareerResumePdfBlobUrl).toHaveBeenCalledWith("resume-1");
    });

    it("handleDownloadPdf は downloadCareerResumePdf を resumeId 付きで呼ぶ", async () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: "resume-1",
          formLocked: false,
          requestLogin,
        }),
      );

      await act(async () => {
        result.current.handleDownloadPdf();
      });

      expect(api.downloadCareerResumePdf).toHaveBeenCalledWith("resume-1");
    });

    it("handleDownloadMarkdown は downloadCareerResumeMarkdown を resumeId 付きで呼ぶ", async () => {
      const requestLogin = vi.fn();
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: "resume-1",
          formLocked: false,
          requestLogin,
        }),
      );

      await act(async () => {
        result.current.handleDownloadMarkdown();
      });

      expect(api.downloadCareerResumeMarkdown).toHaveBeenCalledWith("resume-1");
    });
  });

  describe("exportDisabled の活性制御", () => {
    it("formLocked=true の場合は認証状態・resumeId に関わらず true", () => {
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: "resume-1",
          formLocked: true,
          requestLogin: vi.fn(),
        }),
      );

      expect(result.current.exportDisabled).toBe(true);
    });

    it("未ログインの場合は resumeId が無くても false（ログイン導線として活性化）", () => {
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: false,
          resumeId: null,
          formLocked: false,
          requestLogin: vi.fn(),
        }),
      );

      expect(result.current.exportDisabled).toBe(false);
    });

    it("ログイン済みで resumeId が無い場合は true（未保存のため非活性）", () => {
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: null,
          formLocked: false,
          requestLogin: vi.fn(),
        }),
      );

      expect(result.current.exportDisabled).toBe(true);
    });

    it("ログイン済みで resumeId がある場合は false（活性）", () => {
      const { result } = renderHook(() =>
        useCareerExportActions({
          isAuthenticated: true,
          resumeId: "resume-1",
          formLocked: false,
          requestLogin: vi.fn(),
        }),
      );

      expect(result.current.exportDisabled).toBe(false);
    });
  });
});
