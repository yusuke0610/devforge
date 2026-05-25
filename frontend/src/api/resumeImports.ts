import { NETWORK_MESSAGES } from "../constants/messages";
import { ApiError } from "../utils/appError";
import { API_BASE_URL } from "./client";
import { PATHS } from "./paths";

/** POST /api/resumes/import/extract が返す割り当て候補ブロック */
export type ResumeImportBlock = {
  id: number;
  /** "line"（本文行）| "table"（表セル） */
  kind: string;
  text: string;
};

/** POST /api/resumes/import/extract のレスポンス */
export type ResumeImportBlocksResponse = {
  blocks: ResumeImportBlock[];
};

/**
 * PDF を割り当て候補ブロックに分解して取得する（同期・LLM 不使用）。
 * 取り込み補助 UI が並べて、ユーザーがクリックで各フィールドへ流し込む。
 */
export async function extractResumeBlocks(file: File): Promise<ResumeImportBlocksResponse> {
  const formData = new FormData();
  formData.append("file", file);
  // multipart/form-data は Content-Type を手動指定しない（ブラウザが boundary 付きで設定する）。
  // CSRF トークンは Cookie から取得して X-CSRF-Token ヘッダに付与する。
  const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] ?? "";

  const response = await fetch(`${API_BASE_URL}${PATHS.resumeImports.extract}`, {
    method: "POST",
    headers: { "X-CSRF-Token": csrfToken },
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    let body: { code?: string; message?: string; action?: string } | null = null;
    try {
      body = await response.json();
    } catch {
      // parse 失敗は無視（下の fallback を使う）
    }
    throw new ApiError({
      code: body?.code ?? "INTERNAL_ERROR",
      message: body?.message ?? NETWORK_MESSAGES.REQUEST_FAILED,
      action: body?.action ?? null,
    });
  }

  return response.json() as Promise<ResumeImportBlocksResponse>;
}
