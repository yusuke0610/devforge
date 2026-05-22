import { useCallback, useState } from "react";

import {
  getResumeImportResult,
  getResumeImportStatus,
  startResumeImport,
  type ResumeImportResultResponse,
} from "../../api/resumeImports";
import {
  FALLBACK_MESSAGES,
  INTERNAL_MESSAGES,
  VALIDATION_MESSAGES,
} from "../../constants/messages";
import { type AppErrorState, toAppError } from "../../utils/appError";
import { generateErrorId } from "../../utils/errorId";
import { useTaskPolling } from "../useTaskPolling";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

export type ResumeImportPhase = "idle" | "uploading" | "polling" | "ready" | "error";

type UseResumeImportState = {
  phase: ResumeImportPhase;
  parsedData: ResumeImportResultResponse | null;
  error: AppErrorState | null;
};

export type UseResumeImportReturn = UseResumeImportState & {
  start: (file: File) => Promise<void>;
  reset: () => void;
};

export function useResumeImport(): UseResumeImportReturn {
  const [phase, setPhase] = useState<ResumeImportPhase>("idle");
  const [parsedData, setParsedData] = useState<ResumeImportResultResponse | null>(null);
  const [error, setError] = useState<AppErrorState | null>(null);
  const [importId, setImportId] = useState<string | null>(null);

  const { startPolling } = useTaskPolling({
    checkStatus: async () => {
      if (!importId) throw new Error(INTERNAL_MESSAGES.RESUME_IMPORT_NO_ID);
      return getResumeImportStatus(importId);
    },
    onCompleted: async () => {
      if (!importId) return;
      try {
        const result = await getResumeImportResult(importId);
        setParsedData(result);
        setPhase("ready");
      } catch {
        setError({
          message: FALLBACK_MESSAGES.RESUME_EXTRACT,
          code: "INTERNAL_ERROR",
          action: null,
          retryAfter: null,
          errorId: generateErrorId(),
        });
        setPhase("error");
      }
    },
    onFailed: (err) => {
      setError(err);
      setPhase("error");
    },
    intervalMs: 3000,
  });

  const start = useCallback(
    async (file: File) => {
      // フロントエンド側の事前バリデーション
      if (file.type !== "application/pdf") {
        setError({
          message: VALIDATION_MESSAGES.RESUME_PDF_REQUIRED,
          code: "RESUME_IMPORT_INVALID",
          action: null,
          retryAfter: null,
          errorId: generateErrorId(),
        });
        setPhase("error");
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        setError({
          message: VALIDATION_MESSAGES.RESUME_PDF_SIZE_EXCEEDED,
          code: "RESUME_IMPORT_INVALID",
          action: null,
          retryAfter: null,
          errorId: generateErrorId(),
        });
        setPhase("error");
        return;
      }

      setPhase("uploading");
      setError(null);
      setParsedData(null);

      try {
        const { import_id } = await startResumeImport(file);
        setImportId(import_id);
        setPhase("polling");
        startPolling();
      } catch (err) {
        setError(toAppError(err));
        setPhase("error");
      }
    },
    [startPolling],
  );

  const reset = useCallback(() => {
    setPhase("idle");
    setParsedData(null);
    setError(null);
    setImportId(null);
  }, []);

  return { phase, parsedData, error, start, reset };
}
