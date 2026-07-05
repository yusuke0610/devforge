import { downloadFailureMessage, FALLBACK_MESSAGES } from "../constants/messages";
import { API_BASE_URL, applyCsrfHeader, toApiError } from "./client";

/** リクエストヘッダーを組み立てる（CSRF 付与は client.ts の共有ヘルパーに委譲）。 */
function buildHeaders(options?: RequestInit): Record<string, string> {
  const headers: Record<string, string> = {
    ...((options?.headers as Record<string, string>) ?? {}),
  };
  applyCsrfHeader(headers, options?.method ?? "GET");
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

export async function getBlobUrl(
  url: string,
  options?: RequestInit,
  fallbackMessage: string = FALLBACK_MESSAGES.PREVIEW_FETCH,
): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers: buildHeaders(options),
    credentials: "include",
  });
  if (!response.ok) {
    // AppErrorResponse の code / message / action を保持して呼び出し元の分岐・表示に使う。
    // JSON エラーボディが無い場合の fallback は呼び出し元が用途別に指定できる
    throw await toApiError(response, fallbackMessage);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
