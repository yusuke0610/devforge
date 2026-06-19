import { useState, useEffect, useCallback, useRef } from "react";

import { ApiError, type AppErrorState, toAppError } from "../utils/appError";

interface TaskStatus {
  status: string;
  // backend の Pydantic schema は `str | None`（OpenAPI 生成型では `string | null`）。
  // 生成型 TaskStatusResponse を checkStatus に渡せるよう null を許容する（ADR-0007 論点B）。
  error_message?: string | null;
  error_code?: string | null;
  error_id?: string | null;
  retry_after?: number | null;
}

interface UseTaskPollingOptions {
  /** ステータス取得関数 */
  checkStatus: () => Promise<TaskStatus>;
  /** 完了時コールバック */
  onCompleted: () => void;
  /** 失敗時コールバック */
  onFailed: (error: AppErrorState) => void;
  /** 初回ポーリング間隔（ms、デフォルト: 5000） */
  intervalMs?: number;
  /** バックオフ最大間隔（ms、デフォルト: intervalMs と同値＝バックオフなし） */
  maxIntervalMs?: number;
  /** バックオフ乗数（デフォルト: 1 ＝固定間隔） */
  multiplier?: number;
}

/**
 * バックグラウンドタスクのステータスをポーリングする汎用フック。
 * unmount 時にタイマーをクリアするが、バックエンド処理はそのまま継続される。
 * maxIntervalMs / multiplier を渡すと指数バックオフが有効になる。
 */
export function useTaskPolling(options: UseTaskPollingOptions) {
  const {
    checkStatus,
    onCompleted,
    onFailed,
    intervalMs = 5000,
    maxIntervalMs,
    multiplier = 1,
  } = options;

  const [isPolling, setIsPolling] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const timeoutRef = useRef<number | null>(null);
  // 次回スケジュールに使う現在の間隔（バックオフで変化する）
  const currentIntervalRef = useRef(intervalMs);
  const callbacksRef = useRef({ onCompleted, onFailed, checkStatus });
  const configRef = useRef({
    intervalMs,
    maxIntervalMs: maxIntervalMs ?? intervalMs,
    multiplier,
  });

  // コールバックと設定を ref で最新に保つ
  useEffect(() => {
    callbacksRef.current = { onCompleted, onFailed, checkStatus };
  });
  useEffect(() => {
    configRef.current = {
      intervalMs,
      maxIntervalMs: maxIntervalMs ?? intervalMs,
      multiplier,
    };
  }, [intervalMs, maxIntervalMs, multiplier]);

  const stopPolling = useCallback(() => {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const startPolling = useCallback(() => {
    // バックオフを初期値にリセット
    currentIntervalRef.current = configRef.current.intervalMs;
    setIsPolling(true);
    setStatus("pending");
  }, []);

  useEffect(() => {
    if (!isPolling) return;

    let cancelled = false;

    /**
     * 次回ポーリングをスケジュールし、現在の間隔をバックオフ係数で更新する。
     * - 現在の間隔でスケジュール → その後に乗数を適用
     * - これにより initialInterval が最初の待ち時間になる
     */
    const scheduleNext = () => {
      const { maxIntervalMs: max, multiplier: mult } = configRef.current;
      const current = currentIntervalRef.current;
      currentIntervalRef.current = Math.min(current * mult, max);
      timeoutRef.current = window.setTimeout(poll, current);
    };

    const poll = async () => {
      if (cancelled) return;
      try {
        const data = await callbacksRef.current.checkStatus();
        if (cancelled) return;
        setStatus(data.status);

        if (data.status === "completed") {
          stopPolling();
          callbacksRef.current.onCompleted();
        } else if (data.status === "dead_letter") {
          // dead_letter は失敗の終端状態（リトライ不可 or リトライ枯渇）
          stopPolling();
          callbacksRef.current.onFailed(
            toAppError(
              new ApiError({
                code: data.error_code ?? "INTERNAL_ERROR",
                message: data.error_message || "処理に失敗しました",
                retryAfter:
                  typeof data.retry_after === "number" ? data.retry_after : null,
                errorId: data.error_id,
              }),
            ),
          );
        } else {
          // pending / processing / retrying はポーリング継続
          scheduleNext();
        }
      } catch {
        // ネットワークエラーは無視してリトライ
        if (!cancelled) scheduleNext();
      }
    };

    // 初回即実行
    poll();

    return () => {
      cancelled = true;
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [isPolling, stopPolling]);

  return { startPolling, stopPolling, isPolling, status };
}
