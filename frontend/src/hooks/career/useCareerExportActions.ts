import {
  downloadCareerResumeMarkdown,
  downloadCareerResumePdf,
  getCareerResumePdfBlobUrl,
} from "../../api";
import { SUCCESS_MESSAGES } from "../../constants/messages";
import { usePdfActions } from "../usePdfActions";

type Params = {
  /** 認証状態。未ログインなら各操作はログイン導線へ流す。 */
  isAuthenticated: boolean;
  /** 保存済み経歴書の ID（未保存なら null）。 */
  resumeId: string | null;
  /** ローディング等で操作をブロックしたいときのフラグ。 */
  formLocked: boolean;
  /** 未ログイン時に開くログイン促進モーダル。 */
  requestLogin: () => void;
};

/**
 * 経歴書の出力操作（プレビュー / PDF / Markdown ダウンロード）を一元管理するフック。
 *
 * `usePdfActions` を内包し、職務経歴書の API バインドと「未ログインなら requestLogin、
 * ログイン済みなら resumeId を渡して実行」という認証ゲートをまとめる。
 * CareerResumeForm から出力系の責務を切り離して本体を薄く保つのが目的。
 */
export function useCareerExportActions({ isAuthenticated, resumeId, formLocked, requestLogin }: Params) {
  const {
    downloading,
    previewUrl,
    closePreview,
    onDownloadPdf,
    onDownloadMarkdown,
    onPreviewPdf,
    error,
    success,
  } = usePdfActions({
    downloadPdf: downloadCareerResumePdf,
    downloadMarkdown: downloadCareerResumeMarkdown,
    getPdfBlobUrl: getCareerResumePdfBlobUrl,
  });

  const handlePreview = () => {
    if (!isAuthenticated) return requestLogin();
    if (resumeId) onPreviewPdf(resumeId);
  };
  const handleDownloadPdf = () => {
    if (!isAuthenticated) return requestLogin();
    if (resumeId) onDownloadPdf(resumeId, SUCCESS_MESSAGES.CAREER_PDF_DOWNLOADED);
  };
  const handleDownloadMarkdown = () => {
    if (!isAuthenticated) return requestLogin();
    if (resumeId) onDownloadMarkdown(resumeId);
  };

  // 未ログインでは要ログイン機能ボタンを活性にしてログイン導線にする。
  // ログイン済みでは保存済み（resumeId あり）まで非活性。
  const exportDisabled = formLocked || (isAuthenticated && !resumeId);

  return {
    downloading,
    previewUrl,
    closePreview,
    handlePreview,
    handleDownloadPdf,
    handleDownloadMarkdown,
    exportDisabled,
    error,
    success,
  };
}
