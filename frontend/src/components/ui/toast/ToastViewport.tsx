import { createPortal } from "react-dom";

import { UI_MESSAGES } from "../../../constants/messages";
import type { ToastData } from "./toastContext";
import { ToastItem } from "./ToastItem";
import styles from "./toast.module.css";

type Props = {
  toasts: ToastData[];
  onDismiss: (id: string) => void;
};

/**
 * トーストのスタックを画面右上に固定表示するコンテナ。
 *
 * body 直下にポータルで描画し、各ページのレイアウトや LoadingOverlay 等の
 * スタッキングコンテキストに埋もれないようにする。
 */
export function ToastViewport({ toasts, onDismiss }: Props) {
  if (toasts.length === 0) return null;

  return createPortal(
    <div
      className={styles.viewport}
      role="region"
      aria-label={UI_MESSAGES.TOAST_REGION_LABEL}
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>,
    document.body,
  );
}
