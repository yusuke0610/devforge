import type { CareerFormState } from "../../payloadBuilders";
import type { CareerResumePayload } from "../../types";
import { mergeImportedResume } from "../../formMappers";
import { UI_MESSAGES } from "../../constants/messages";
import styles from "./ResumeImportConfirmModal.module.css";

type Props = {
  parsedData: CareerResumePayload;
  existingForm: CareerFormState;
  isDirty: boolean;
  onConfirm: (merged: CareerFormState) => void;
  onCancel: () => void;
};

/**
 * インポート内容プレビューと反映確認モーダル。
 * 「反映する」クリックで mergeImportedResume の結果を onConfirm に渡す。
 */
export function ResumeImportConfirmModal({
  parsedData,
  existingForm,
  isDirty,
  onConfirm,
  onCancel,
}: Props) {
  const handleConfirm = () => {
    const merged = mergeImportedResume(existingForm, parsedData);
    onConfirm(merged);
  };

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <h2 className={styles.title}>PDF から読み取った内容</h2>

        <div className={styles.preview}>
          {parsedData.full_name && (
            <div className={styles.row}>
              <span className={styles.label}>氏名</span>
              <span className={styles.value}>{parsedData.full_name}</span>
            </div>
          )}
          {parsedData.career_summary && (
            <div className={styles.row}>
              <span className={styles.label}>職務要約</span>
              <span className={styles.value}>{parsedData.career_summary.slice(0, 100)}{parsedData.career_summary.length > 100 ? "…" : ""}</span>
            </div>
          )}
          <div className={styles.row}>
            <span className={styles.label}>職務経歴</span>
            <span className={styles.value}>{parsedData.experiences.length} 件</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>資格</span>
            <span className={styles.value}>{parsedData.qualifications.length} 件</span>
          </div>
          {parsedData.self_pr && (
            <div className={styles.row}>
              <span className={styles.label}>自己PR</span>
              <span className={styles.value}>{parsedData.self_pr.slice(0, 80)}{parsedData.self_pr.length > 80 ? "…" : ""}</span>
            </div>
          )}
        </div>

        {isDirty && <p className={styles.warning}>{UI_MESSAGES.RESUME_IMPORT_OVERWRITE_WARNING}</p>}
        {!isDirty && <p className={styles.info}>{UI_MESSAGES.RESUME_IMPORT_APPLY_INFO}</p>}

        <div className={styles.actions}>
          <button type="button" className="primary" onClick={handleConfirm}>
            反映する
          </button>
          <button type="button" onClick={onCancel}>
            キャンセル
          </button>
        </div>
      </div>
    </div>
  );
}
