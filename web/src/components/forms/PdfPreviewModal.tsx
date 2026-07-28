import type { ReactNode } from "react";

import styles from "./PdfPreviewModal.module.css";

export function PdfPreviewModal({
  previewUrl,
  onClose,
  headerAction,
}: {
  previewUrl: string;
  onClose: () => void;
  /** ヘッダーに置く任意のアクション（例: ドラフトの「フォームに反映」/ ADR-0025）。 */
  headerAction?: ReactNode;
}) {
  return (
    <div className={styles.previewOverlay} onClick={onClose}>
      <div className={styles.previewModal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.previewHeader}>
          <span>PDFプレビュー</span>
          <div className={styles.previewHeaderActions}>
            {headerAction}
            <button type="button" onClick={onClose}>
              閉じる
            </button>
          </div>
        </div>
        <iframe src={previewUrl} className={styles.previewFrame} title="PDF Preview" />
      </div>
    </div>
  );
}
