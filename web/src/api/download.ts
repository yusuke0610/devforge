import { downloadFailureMessage, FALLBACK_MESSAGES } from "../constants/messages";
import { API_BASE_URL, getCsrfToken, toApiError } from "./client";

/** 状態変更メソッドなら CSRF トークン付きヘッダーを組み立てる（client.ts の request() と同じ契約）。 */
function buildHeaders(options?: RequestInit): Record<string, string> {
  const method = (options?.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    ...((options?.headers as Record<string, string>) ?? {}),
  };
  if (["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
    headers["X-CSRF-Token"] = getCsrfToken();
  }
  return headers;
}

export async function downloadBlob(
  url: string,
  filename: string,
  options?: RequestInit,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: buildHeaders(options),
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(downloadFailureMessage(filename));
  }
  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(blobUrl);
}

export async function getBlobUrl(url: string, options?: RequestInit): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: buildHeaders(options),
    credentials: "include",
  });
  if (!response.ok) {
    // AppErrorResponse の code / message / action を保持して呼び出し元の分岐・表示に使う
    throw await toApiError(response, FALLBACK_MESSAGES.PREVIEW_FETCH);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
