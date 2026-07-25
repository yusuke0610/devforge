import { useCallback, useState } from "react";

import { importResumePdf } from "../api/agent";
import { toAppError, type AppErrorState } from "../api";
import type { ResumeImportResponse } from "../api/types";
import { FALLBACK_MESSAGES } from "../constants/messages";

/**
 * 手持ち PDF 経歴書のアップロード → 構造化抽出を管理するフック（ADR-0024 / #528）。
 *
 * アップロード状態（importing）とエラー（AppErrorState）を持ち、成功時は抽出 payload を返す。
 * 抽出結果のフォーム適用（注入・上書き確認）は呼び出し側が担う（本フックは API 呼び出しと
 * 状態管理のみ / DB 非更新 / ADR-0010）。失敗時は backend の日本語メッセージをそのまま表示する。
 */
export function useResumeImport() {
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<AppErrorState | null>(null);

  const importPdf = useCallback(
    async (file: File): Promise<ResumeImportResponse | null> => {
      setImporting(true);
      setError(null);
      try {
        return await importResumePdf(file);
      } catch (e) {
        // 422（非対応/破損 PDF・サイズ超過）/ 502（抽出失敗）/ 429 は backend の message を表示する
        setError(toAppError(e, FALLBACK_MESSAGES.RESUME_IMPORT));
        return null;
      } finally {
        setImporting(false);
      }
    },
    [],
  );

  const clearError = useCallback(() => setError(null), []);

  return { importing, error, importPdf, clearError };
}
