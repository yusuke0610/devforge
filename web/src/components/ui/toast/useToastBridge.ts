import { useEffect, useRef } from "react";

import type { AppErrorState } from "../../../utils/appError";
import { useToast, type ToastVariant } from "./toastContext";

/**
 * 文字列メッセージの state を監視し、非 null になるたびトーストを出す表示層ブリッジ。
 *
 * 各フック（useDocumentForm / usePdfActions 等）は従来通り
 * error / success 文字列を保持し続ける。本ブリッジはそれをトーストへ橋渡しするだけの薄いアダプタで、
 * フック側を Provider に依存させずユニットテスト可能なまま保つ。
 *
 * - React StrictMode による effect 二重実行や、同一文言が連続するケースでの二重表示を ref でガードする。
 * - message が空（null / undefined / 空文字）に戻ったら ref をリセットし、
 *   同じ文言が再び現れたときに再表示できるようにする。
 */
export function useMessageToast(
  message: string | null | undefined,
  variant: ToastVariant,
): void {
  const { showSuccess, showError } = useToast();
  const lastShownRef = useRef<string | null>(null);

  useEffect(() => {
    if (!message) {
      lastShownRef.current = null;
      return;
    }
    if (message === lastShownRef.current) return;
    lastShownRef.current = message;
    if (variant === "success") {
      showSuccess(message);
    } else {
      showError(message);
    }
  }, [message, variant, showSuccess, showError]);
}

/**
 * {@link AppErrorState} の state を監視し、新しいエラーが現れるたびエラートーストを出すブリッジ。
 * 同一エラーの二重表示は errorId で防ぐ。useAsyncTaskPage のような構造化エラーを扱うページで使う。
 */
export function useAppErrorToast(error: AppErrorState | null | undefined): void {
  const { showError } = useToast();
  const lastErrorIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!error) {
      lastErrorIdRef.current = null;
      return;
    }
    // errorId は AppErrorState では必須だが、万一空の場合は重複判定の基準にできないため毎回表示する
    // （空文字どうしが `===` で一致して別エラーを取りこぼすのを防ぐ防御）。
    if (!error.errorId) {
      showError(error);
      return;
    }
    if (error.errorId === lastErrorIdRef.current) return;
    lastErrorIdRef.current = error.errorId;
    showError(error);
  }, [error, showError]);
}
