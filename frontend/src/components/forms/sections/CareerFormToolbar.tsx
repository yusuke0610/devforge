import { UI_MESSAGES } from "../../../constants/messages";
import { SaveIcon } from "../../icons/SaveIcon";
import { EyeIcon } from "../../icons/EyeIcon";
import { TrashIcon } from "../../icons/TrashIcon";
import { PdfDownloadIcon } from "../../icons/PdfDownloadIcon";
import { MarkdownDownloadIcon } from "../../icons/MarkdownDownloadIcon";
import shared from "../../../styles/shared.module.css";
import layout from "../CareerResumeForm.module.css";

type Props = {
  /** 保存ボタンのラベル（保存 / 更新）。 */
  saveButtonText: string;
  /** 保存可能か（マスタ含むデータが揃っているか）。 */
  canSubmit: boolean;
  /** 保存処理中。 */
  saving: boolean;
  /** プレビュー / PDF / Markdown の出力ボタンを非活性にするか。 */
  exportDisabled: boolean;
  /** PDF ダウンロード処理中。 */
  downloading: boolean;
  /** 削除ボタンを非活性にするか。 */
  deleteDisabled: boolean;
  onPreview: () => void;
  onDownloadPdf: () => void;
  onDownloadMarkdown: () => void;
  onDelete: () => void;
};

/**
 * 職務経歴書フォームのヘッダーツールバー（保存・プレビュー・PDF・Markdown・削除）。
 *
 * 表示専用。保存ボタンは form の submit、それ以外は親から渡されたハンドラを呼ぶだけで、
 * 認証ゲートや出力ロジックは {@link useCareerExportActions} 側が担う。
 */
export function CareerFormToolbar({
  saveButtonText,
  canSubmit,
  saving,
  exportDisabled,
  downloading,
  deleteDisabled,
  onPreview,
  onDownloadPdf,
  onDownloadMarkdown,
  onDelete,
}: Props) {
  return (
    <div className={shared.pageHeader}>
      <h1>{UI_MESSAGES.CAREER_RESUME_TITLE}</h1>
      <div className={shared.pageHeaderActions}>
        {/* ファイル取り込みは右カラムの原本ビュー（ドラッグ&ドロップ / クリック）に集約。 */}
        <button
          type="submit"
          className={`primary ${layout.iconButton}`}
          disabled={!canSubmit || saving}
          aria-label={saveButtonText}
          title={saveButtonText}
        >
          {saving ? (
            <span className={layout.buttonSpinner} aria-hidden="true" />
          ) : (
            <SaveIcon className={layout.headerIcon} />
          )}
        </button>
        <button
          type="button"
          className={layout.iconButton}
          onClick={onPreview}
          disabled={exportDisabled}
          aria-label={UI_MESSAGES.RESUME_PREVIEW}
          title={UI_MESSAGES.RESUME_PREVIEW}
        >
          <EyeIcon className={layout.headerIcon} />
        </button>
        <button
          type="button"
          className={layout.iconButton}
          onClick={onDownloadPdf}
          disabled={exportDisabled || downloading}
          aria-label={UI_MESSAGES.RESUME_EXPORT_PDF}
          title={UI_MESSAGES.RESUME_EXPORT_PDF}
        >
          {downloading ? (
            <span className={layout.buttonSpinner} aria-hidden="true" />
          ) : (
            <PdfDownloadIcon className={layout.headerIcon} />
          )}
        </button>
        <button
          type="button"
          className={layout.iconButton}
          onClick={onDownloadMarkdown}
          disabled={exportDisabled}
          aria-label={UI_MESSAGES.RESUME_EXPORT_MARKDOWN}
          title={UI_MESSAGES.RESUME_EXPORT_MARKDOWN}
        >
          <MarkdownDownloadIcon className={layout.headerIcon} />
        </button>
        <button
          type="button"
          className={`danger ${layout.iconButton}`}
          onClick={onDelete}
          disabled={deleteDisabled}
          aria-label={UI_MESSAGES.RESUME_DELETE_ALL}
          title={UI_MESSAGES.RESUME_DELETE_ALL}
        >
          <TrashIcon className={layout.headerIcon} />
        </button>
      </div>
    </div>
  );
}
