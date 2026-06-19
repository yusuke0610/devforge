import styles from "./PdfPreviewModal.module.css";

export function PdfPreviewModal({
  previewUrl,
  onClose,
}: {
  previewUrl: string;
  onClose: () => void;
}) {
  return (
    <div className={styles.previewOverlay} onClick={onClose}>
      <div className={styles.previewModal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.previewHeader}>
          <span>PDFプレビュー</span>
          <button type="button" onClick={onClose}>
            閉じる
          </button>
        </div>
        <iframe src={previewUrl} className={styles.previewFrame} title="PDF Preview" />
      </div>
    </div>
  );
}
