import { useCallback, useEffect, useState } from "react";

import {
  getResumeImportResult,
  startResumeImport,
  type ResumeImportResultResponse,
} from "../../api/resumeImports";
import {
  FALLBACK_MESSAGES,
  VALIDATION_MESSAGES,
} from "../../constants/messages";
import {
  beginPolling,
  beginUpload,
  clearImport,
  setError,
  type ResumeImportPhase,
} from "../../store/resumeImportSlice";
import { useAppDispatch, useAppSelector } from "../../store";
import { type AppErrorState, toAppError } from "../../utils/appError";
import { generateErrorId } from "../../utils/errorId";

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

export type { ResumeImportPhase };

export type UseResumeImportReturn = {
  /** 進行フェーズ（Redux 由来） */
  phase: ResumeImportPhase;
  /** プレビュー用に取得した解析結果（コンポーネントローカル） */
  parsedData: ResumeImportResultResponse | null;
  /** エラー情報（Redux 由来） */
  error: AppErrorState | null;
  /** PDF アップロードを開始する */
  start: (file: File) => Promise<void>;
  /** import 状態を初期化する */
  reset: () => void;
};

/**
 * 職務経歴書 PDF インポートのフロント側エントリーポイント。
 *
 * - 進行フェーズ・importId・エラーは Redux + redux-persist に置く
 *   （他タブ遷移・ページリロードを跨いで保持される）。
 * - 実際のポーリングは `ResumeImportPoller`（AuthenticatedLayout 配下）が行う。
 *   本フックはアップロード開始と結果取得・モーダル制御のみを担う。
 */
export function useResumeImport(): UseResumeImportReturn {
  const dispatch = useAppDispatch();
  const phase = useAppSelector((s) => s.resumeImport.phase);
  const importId = useAppSelector((s) => s.resumeImport.importId);
  const error = useAppSelector((s) => s.resumeImport.error);
  // parsedData は importId と紐付けて保持する。importId が変わったり null になったりすると
  // 自動的に「parsedData は無い」扱いになり、別 effect でクリアする必要がない。
  const [parsedSnapshot, setParsedSnapshot] = useState<{
    importId: string;
    data: ResumeImportResultResponse;
  } | null>(null);
  const parsedData =
    parsedSnapshot && parsedSnapshot.importId === importId
      ? parsedSnapshot.data
      : null;

  // phase が "ready" になったら、解析結果を API から取得してローカルに保持する。
  // PII を含むため Redux には置かない。
  useEffect(() => {
    if (phase !== "ready" || !importId) return;
    let cancelled = false;
    (async () => {
      try {
        const result = await getResumeImportResult(importId);
        if (!cancelled) setParsedSnapshot({ importId, data: result });
      } catch {
        if (!cancelled) {
          dispatch(
            setError({
              code: "INTERNAL_ERROR",
              message: FALLBACK_MESSAGES.RESUME_EXTRACT,
              action: null,
              retryAfter: null,
              errorId: generateErrorId(),
            }),
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [phase, importId, dispatch]);

  const start = useCallback(
    async (file: File) => {
      // フロントエンド側の事前バリデーション
      if (file.type !== "application/pdf") {
        dispatch(
          setError({
            code: "RESUME_IMPORT_INVALID",
            message: VALIDATION_MESSAGES.RESUME_PDF_REQUIRED,
            action: null,
            retryAfter: null,
            errorId: generateErrorId(),
          }),
        );
        return;
      }
      if (file.size > MAX_FILE_SIZE) {
        dispatch(
          setError({
            code: "RESUME_IMPORT_INVALID",
            message: VALIDATION_MESSAGES.RESUME_PDF_SIZE_EXCEEDED,
            action: null,
            retryAfter: null,
            errorId: generateErrorId(),
          }),
        );
        return;
      }

      dispatch(beginUpload());

      try {
        const { import_id } = await startResumeImport(file);
        dispatch(beginPolling({ importId: import_id }));
      } catch (err) {
        const appError = toAppError(err);
        dispatch(setError(appError));
      }
    },
    [dispatch],
  );

  const reset = useCallback(() => {
    dispatch(clearImport());
  }, [dispatch]);

  // Redux state の error は plain object。AppErrorState 互換なのでそのまま返す。
  return { phase, parsedData, error, start, reset };
}
