import { downloadFailureMessage, FALLBACK_MESSAGES } from "../constants/messages";
import { API_BASE_URL } from "./client";

export async function downloadBlob(
  url: string,
  filename: string,
  options?: RequestInit,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
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

export async function getBlobUrl(url: string): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error(FALLBACK_MESSAGES.PREVIEW_FETCH);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}
