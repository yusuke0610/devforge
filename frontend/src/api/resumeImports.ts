import type { CareerResumePayload } from "../types";
import { ApiError } from "../utils/appError";
import { API_BASE_URL, request } from "./client";
import { PATHS } from "./paths";

/** POST /api/resumes/import のレスポンス */
type ResumeImportStartResponse = {
  import_id: string;
};

/** GET /api/resumes/import/{id}/status のレスポンス */
export type ResumeImportStatusResponse = {
  status: string;
  error_message?: string;
  error_code?: string;
  judge_reason?: string;
};

/** GET /api/resumes/import/{id}/result のレスポンス */
export type ResumeImportResultResponse = {
  result: CareerResumePayload;
  is_resume: boolean;
  judge_reason?: string;
};

/** PDF をアップロードしてインポートタスクを開始する。 */
export async function startResumeImport(file: File): Promise<ResumeImportStartResponse> {
  const formData = new FormData();
  formData.append("file", file);

  // multipart/form-data は Content-Type を手動で指定しない（ブラウザが boundary 付きで設定する）
  // CSRF トークンは Cookie から取得して X-CSRF-Token ヘッダに付与する
  const csrfToken = document.cookie.match(/csrf_token=([^;]+)/)?.[1] ?? "";

  const response = await fetch(`${API_BASE_URL}${PATHS.resumeImports.start}`, {
    method: "POST",
    headers: {
      "X-CSRF-Token": csrfToken,
    },
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    let body: { code?: string; message?: string; action?: string } | null = null;
    try {
      body = await response.json();
    } catch {
      // parse 失敗は無視
    }
    throw new ApiError({
      code: body?.code ?? "INTERNAL_ERROR",
      message: body?.message ?? "アップロードに失敗しました。",
      action: body?.action ?? null,
    });
  }

  return response.json() as Promise<ResumeImportStartResponse>;
}

/** インポートタスクのステータスをポーリングする。 */
export async function getResumeImportStatus(
  importId: string,
): Promise<ResumeImportStatusResponse> {
  return request<ResumeImportStatusResponse>(PATHS.resumeImports.status(importId));
}

/** 抽出結果を取得する（completed のみ 200）。 */
export async function getResumeImportResult(
  importId: string,
): Promise<ResumeImportResultResponse> {
  return request<ResumeImportResultResponse>(PATHS.resumeImports.result(importId));
}
