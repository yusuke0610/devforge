import { useEffect } from "react";

import {
  getResumeImportProgress,
  getResumeImportStatus,
} from "../api/resumeImports";
import { INTERNAL_MESSAGES } from "../constants/messages";
import { useAppDispatch, useAppSelector } from "../store";
import { markReady, setError, setProgress } from "../store/resumeImportSlice";
import { useTaskPolling } from "../hooks/useTaskPolling";

/**
 * 職務経歴書 PDF インポートの全タブ共通ポーラー。
 *
 * AuthenticatedLayout 配下に常駐し、Redux の `resumeImport.phase` が "polling"
 * の間だけバックエンドのタスクステータスをポーリングする。職務経歴書タブから
 * 他タブに遷移しても本コンポーネントはアンマウントされないため、解析処理は
 * 継続観測される（バックエンド側は元々非同期で走り続ける）。
 *
 * status と progress を Promise.allSettled で並走取得する。progress 取得失敗は
 * ポーリング本体に影響させない（Redis 障害時の graceful degradation）。
 *
 * 解析完了 → markReady() で phase を "ready" に遷移。
 * 結果データの取得は CareerResumeForm 側で行う（PII を Redux に乗せないため）。
 */
export function ResumeImportPoller() {
  const dispatch = useAppDispatch();
  const phase = useAppSelector((s) => s.resumeImport.phase);
  const importId = useAppSelector((s) => s.resumeImport.importId);

  const { startPolling, stopPolling } = useTaskPolling({
    checkStatus: async () => {
      if (!importId) throw new Error(INTERNAL_MESSAGES.RESUME_IMPORT_NO_ID);
      // status と progress を並走取得。progress 失敗はポーリング本体に伝播させない。
      const [statusResult, progressResult] = await Promise.allSettled([
        getResumeImportStatus(importId),
        getResumeImportProgress(importId),
      ]);

      if (progressResult.status === "fulfilled") {
        dispatch(setProgress(progressResult.value));
      }

      if (statusResult.status === "rejected") {
        throw statusResult.reason;
      }
      return statusResult.value;
    },
    onCompleted: () => {
      dispatch(markReady());
    },
    onFailed: (err) => {
      dispatch(setError(err));
    },
    intervalMs: 3000,
  });

  // phase === "polling" のときだけポーリングを稼働させる。
  // ページリロードで redux-persist から polling 状態が復元された場合も
  // この effect が走って自動再開する。
  useEffect(() => {
    if (phase === "polling" && importId) {
      startPolling();
      return () => stopPolling();
    }
    // それ以外のフェーズではポーラーは停止
    return undefined;
  }, [phase, importId, startPolling, stopPolling]);

  return null;
}
