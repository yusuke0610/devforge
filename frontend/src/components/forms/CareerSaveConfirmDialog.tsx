import { DIFF_DIALOG_MESSAGES as D } from "../../constants/messages";
import type { CareerChange, ChangeKind } from "../../utils/careerDiff";
import styles from "./CareerSaveConfirmDialog.module.css";

/** 種別ごとのバッジ文言。 */
const KIND_LABEL: Record<ChangeKind, string> = {
  modified: D.MODIFIED_LABEL,
  added: D.ADDED_LABEL,
  removed: D.REMOVED_LABEL,
};

/**
 * 経歴書 保存時の変更点確認ダイアログ。
 * baseline と編集中フォームの差分（旧→新／追加・削除・修正）を一覧表示し、
 * 各行で「元に戻す」（項目別ロールバック）を実行できる。
 */
export function CareerSaveConfirmDialog({
  changes,
  saving,
  onConfirm,
  onCancel,
  onRollback,
}: {
  changes: CareerChange[];
  saving: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onRollback: (change: CareerChange) => void;
}) {
  const hasChanges = changes.length > 0;

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div
        className={styles.dialog}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={D.TITLE}
      >
        <h2 className={styles.title}>{D.TITLE}</h2>
        <p className={styles.description}>{D.DESCRIPTION}</p>

        {hasChanges ? (
          <ul className={styles.list}>
            {changes.map((change) => (
              <li key={`${change.path.join("/")}:${change.kind}`} className={styles.row}>
                <div className={styles.rowMain}>
                  <div className={styles.rowHead}>
                    <span className={`${styles.badge} ${styles[change.kind]}`}>
                      {KIND_LABEL[change.kind]}
                    </span>
                    <span className={styles.label}>{change.label}</span>
                  </div>
                  <div className={styles.values}>
                    {change.kind !== "added" && (
                      <span className={styles.oldValue}>{change.oldValue || D.EMPTY_VALUE}</span>
                    )}
                    {change.kind === "modified" && <span className={styles.arrow}>→</span>}
                    {change.kind !== "removed" && (
                      <span className={styles.newValue}>{change.newValue || D.EMPTY_VALUE}</span>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  className={styles.rollback}
                  onClick={() => onRollback(change)}
                  disabled={saving}
                >
                  {D.ROLLBACK}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <p className={styles.empty}>{D.NO_CHANGES}</p>
        )}

        <div className={styles.actions}>
          <button
            type="button"
            className="primary"
            onClick={onConfirm}
            disabled={saving || !hasChanges}
          >
            {D.CONFIRM}
          </button>
          <button type="button" onClick={onCancel} disabled={saving}>
            {D.CANCEL}
          </button>
        </div>
      </div>
    </div>
  );
}
