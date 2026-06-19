import { createContext, useContext } from "react";

import type { AppErrorState } from "../../../utils/appError";

/** トーストの種別。success は自動消去、error は手動クローズ。 */
export type ToastVariant = "success" | "error";

/** 表示中のトースト 1 件分のデータ。 */
export type ToastData = {
  id: string;
  variant: ToastVariant;
  message: string;
  /**
   * 構造化エラー（{@link AppErrorState}）由来の場合のみ設定される。
   * ERROR_CONFIG の回復アクション解決に使う。
   */
  code?: string;
  /** API が返した補足アクション文言（AppErrorState 由来）。 */
  action?: string | null;
  /** エラー追跡用の ID（AppErrorState 由来）。 */
  errorId?: string;
};

/** {@link useToast} が返すトースト操作 API。 */
export type ToastContextValue = {
  /** 成功トーストを表示する（一定時間で自動消去される）。 */
  showSuccess: (message: string) => void;
  /**
   * エラートーストを表示する（手動で閉じるまで残る）。
   * 文字列（frontend 完結のメッセージ）と {@link AppErrorState}（API 由来）の両方を受け付ける。
   */
  showError: (error: string | AppErrorState) => void;
  /** 指定 ID のトーストを閉じる。 */
  dismiss: (id: string) => void;
};

/** 成功トーストが自動消去されるまでの時間（ms）。 */
export const SUCCESS_TOAST_DURATION_MS = 4000;

export const ToastContext = createContext<ToastContextValue | null>(null);

/**
 * トースト表示 API を取得するフック。{@link ToastProvider} 配下でのみ利用できる。
 */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    // 開発者向け内部エラー（英語）: Provider 外で呼ばれた配線ミスを握りつぶさず即座に気付けるようにする。
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
