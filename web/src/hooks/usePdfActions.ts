import { useState } from "react";

import { FALLBACK_MESSAGES } from "../constants/messages";

/**
 * PDF・Markdown のダウンロードおよびプレビュー操作を提供するカスタムフック。
 * error / success はフック内部で管理し、呼び出し元で setError / setSuccess を渡す必要はない。
 */
export function usePdfActions({
  downloadPdf,
  downloadMarkdown,
  getPdfBlobUrl,
}: {
  downloadPdf: (id: string) => Promise<void>;
  downloadMarkdown: (id: string) => Promise<void>;
  getPdfBlobUrl: (id: string) => Promise<string>;
}) {
  const [downloading, setDownloading] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  /** プレビューを閉じ、Blob URL を解放する。 */
  const closePreview = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
  };

  /** error / success メッセージをリセットする。 */
  const clearMessages = () => {
    setError(null);
    setSuccess(null);
  };

  /**
   * PDF をダウンロードする。
   * @param id ドキュメント ID
   * @param successMessage 成功時に表示するメッセージ
   */
  const onDownloadPdf = async (id: string, successMessage: string) => {
    setDownloading(true);
    setError(null);
    setSuccess(null);
    try {
      await downloadPdf(id);
      setSuccess(successMessage);
    } catch (e) {
      setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.PDF_DOWNLOAD);
    } finally {
      setDownloading(false);
    }
  };

  /**
   * Markdown をダウンロードする。
   * @param id ドキュメント ID
   */
  const onDownloadMarkdown = async (id: string) => {
    setError(null);
    try {
      await downloadMarkdown(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.MARKDOWN_DOWNLOAD);
    }
  };

  /**
   * PDF プレビューを開く。
   * @param id ドキュメント ID
   */
  const onPreviewPdf = async (id: string) => {
    setError(null);
    try {
      const url = await getPdfBlobUrl(id);
      setPreviewUrl(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.PREVIEW);
    }
  };

  return {
    downloading,
    previewUrl,
    closePreview,
    onDownloadPdf,
    onDownloadMarkdown,
    onPreviewPdf,
    error,
    success,
    clearMessages,
  };
}
