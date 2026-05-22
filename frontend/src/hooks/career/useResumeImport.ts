import { useCallback, useState } from "react";

import {
  getResumeImportResult,
  getResumeImportStatus,
  startResumeImport,
  type ResumeImportResultResponse,
} from "../../api/resumeImports";
import type { AppErrorState } from "../../utils/appError";
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
      if (!importId) throw new Error("import_id が未設定です");
      return getResumeImportStatus(importId);
    },
    onCompleted: async () => {
      if (!importId) return;
      try {
        const result = await getResumeImportResult(importId);
        setParsedData(result);
        setPhase("ready");
      } catch {
        setError({ message: "抽出結果の取得に失敗しました。", code: "INTERNAL_ERROR", action: null });
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
        setError({ message: "PDF をアップロードしてください。", code: "RESUME_IMPORT_INVALID", action: null });
        setPhase("error");
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        setError({ message: "10 MB 以下の PDF をアップロードしてください。", code: "RESUME_IMPORT_INVALID", action: null });
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
        const { toAppError } = await import("../../utils/appError");
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
