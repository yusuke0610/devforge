import { useEffect } from "react";

import { isErrorCode } from "../../../constants/errorCodes";
import { ERROR_CONFIG } from "../../../constants/errorMessages";
import { UI_MESSAGES } from "../../../constants/messages";
import { SUCCESS_TOAST_DURATION_MS, type ToastData } from "./toastContext";
import styles from "./toast.module.css";

type Props = {
  toast: ToastData;
  onDismiss: (id: string) => void;
};

/**
 * 単一トーストのカード。
 *
 * - success: {@link SUCCESS_TOAST_DURATION_MS} 経過で自動消去（× ボタンでも閉じられる）。
 * - error: 自動消去せず × ボタンで手動クローズする。AppErrorState 由来（code あり）の場合は
 *   ERROR_CONFIG の回復アクション・補足アクション文言・エラー ID も表示する。
 */
export function ToastItem({ toast, onDismiss }: Props) {
  const { id, variant, message, code, action, errorId } = toast;

  // 成功トーストのみ一定時間で自動消去する。
  useEffect(() => {
    if (variant !== "success") return;
    const timer = window.setTimeout(() => onDismiss(id), SUCCESS_TOAST_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [variant, id, onDismiss]);

  // 構造化エラー（code あり）のときだけ回復アクションを解決する。
  // 文字列エラー（frontend 完結メッセージ）には回復ボタンを出さない。
  const recovery = code
    ? (isErrorCode(code) ? ERROR_CONFIG[code] : ERROR_CONFIG.INTERNAL_ERROR).recovery
    : null;

  return (
    <div
      className={`${styles.toast} ${variant === "success" ? styles.success : styles.error}`}
      role={variant === "error" ? "alert" : "status"}
    >
      <div className={styles.body}>
        <p className={styles.message}>{message}</p>
        {(recovery || action) && (
          <div className={styles.actions}>
            {recovery && (
              <button
                type="button"
                className={styles.actionButton}
                onClick={recovery.fn ?? undefined}
                disabled={!recovery.fn}
              >
                {recovery.label}
              </button>
            )}
            {action && <p className={styles.actionText}>{action}</p>}
          </div>
        )}
        {errorId && (
          <p className={styles.errorId}>
            {UI_MESSAGES.TOAST_ERROR_ID_LABEL} {errorId}
          </p>
        )}
      </div>
      <button
        type="button"
        className={styles.dismiss}
        onClick={() => onDismiss(id)}
        aria-label={UI_MESSAGES.TOAST_DISMISS}
      >
        ×
      </button>
    </div>
  );
}
