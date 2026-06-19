import { useCallback, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import type { AppErrorState } from "../../../utils/appError";
import {
  ToastContext,
  type ToastContextValue,
  type ToastData,
} from "./toastContext";
import { ToastViewport } from "./ToastViewport";

/**
 * アプリ全体のトースト表示を司る Provider。
 *
 * 成功/エラーの一時通知をスタック管理し、{@link ToastViewport} を body 直下のポータルに描画する。
 * 各画面のフックが従来通り保持する error/success state は、表示層の {@link useMessageToast} /
 * {@link useAppErrorToast} ブリッジ経由でこの Provider に橋渡しされる。
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastData[]>([]);
  // トースト ID の単調増加カウンタ。同一ミリ秒の連続発行でも衝突しないようにする。
  const seqRef = useRef(0);

  const nextId = useCallback(() => {
    seqRef.current += 1;
    return `toast-${seqRef.current}`;
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const showSuccess = useCallback(
    (message: string) => {
      setToasts((prev) => [...prev, { id: nextId(), variant: "success", message }]);
    },
    [nextId],
  );

  const showError = useCallback(
    (error: string | AppErrorState) => {
      const toast: ToastData =
        typeof error === "string"
          ? { id: nextId(), variant: "error", message: error }
          : {
              id: nextId(),
              variant: "error",
              message: error.message,
              code: error.code,
              action: error.action,
              errorId: error.errorId,
            };
      setToasts((prev) => [...prev, toast]);
    },
    [nextId],
  );

  const value = useMemo<ToastContextValue>(
    () => ({ showSuccess, showError, dismiss }),
    [showSuccess, showError, dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}
