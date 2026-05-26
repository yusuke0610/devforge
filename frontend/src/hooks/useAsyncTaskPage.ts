import { useState, useEffect, useCallback } from "react";
import type { Dispatch, SetStateAction } from "react";
import { useTaskPolling } from "./useTaskPolling";
import type { AppErrorState } from "../utils/appError";
import { isInProgressStatus } from "../utils/taskStatus";
import type { TaskProgress } from "../api/githubLink";

/** 非同期タスクページのフェーズ型 */
export type AsyncTaskPhase = "loading-cache" | "input" | "polling" | "result";

/** 指数バックオフのデフォルト設定 */
const POLLING_CONFIG = {
  /** 初回ポーリング間隔（ms） */
  initialInterval: 1000,
  /** ポーリング最大間隔（ms） */
  maxInterval: 10000,
  /** バックオフ乗数 */
  multiplier: 1.5,
} as const;

const getNextInterval = (current: number): number =>
  Math.min(current * POLLING_CONFIG.multiplier, POLLING_CONFIG.maxInterval);

// getNextInterval は将来の拡張用に export しておく
export { getNextInterval };

/** useAsyncTaskPage のオプション型 */
export type UseAsyncTaskPageOptions<TResult> = {
  /**
   * キャッシュ読み込み関数。
   * - 結果が存在する場合は result を返す
   * - 処理中の場合は status: "pending" | "processing" を返す
   * - キャッシュなしの場合は result: null を返す
   */
  loadCache: () => Promise<{
    result: TResult | null;
    status?: string;
  }>;
  /**
   * タスクステータス取得関数（ポーリング用）。
   */
  checkStatus: () => Promise<{ status: string; error_message?: string; error_code?: string }>;
  /**
   * 進捗取得関数（オプション）。
   * 指定した場合、ポーリングのたびに並走して呼ばれる。
   * 失敗してもポーリング本体には影響しない。
   */
  fetchProgress?: () => Promise<TaskProgress>;
};

/** useAsyncTaskPage の戻り値型 */
type UseAsyncTaskPageReturn<TResult> = {
  /** 現在のフェーズ */
  phase: AsyncTaskPhase;
  /** フェーズを手動で更新する関数 */
  setPhase: Dispatch<SetStateAction<AsyncTaskPhase>>;
  /** 結果（result フェーズ時のみ非 null） */
  result: TResult | null;
  /** 結果を更新する関数 */
  setResult: Dispatch<SetStateAction<TResult | null>>;
  /** エラーメッセージ */
  error: AppErrorState | null;
  /** エラーを更新する関数 */
  setError: Dispatch<SetStateAction<AppErrorState | null>>;
  /** ポーリング開始関数 */
  startPolling: () => void;
  /** ポーリング中フラグ */
  isPolling: boolean;
  /**
   * リクエストを送信した後に呼ぶハンドラ。
   * polling フェーズに遷移してポーリングを開始する。
   */
  transitionToPolling: () => void;
  /**
   * 結果画面から入力画面に戻るハンドラ。
   * result と追加状態をリセットする。
   */
  backToInput: () => void;
  /**
   * 現在の進捗情報。fetchProgress が未指定または取得失敗時は null。
   */
  progress: TaskProgress | null;
};

/**
 * 非同期タスクページで共通する phase 管理・ポーリング制御・エラー処理を提供するカスタムフック。
 * GitHubLinkDashboard など、
 * 「キャッシュ読み込み → 入力 → ポーリング → 結果」の状態遷移を持つページで利用する。
 *
 * fetchProgress を渡すと、ポーリングのたびに進捗も取得して progress に反映する。
 * Redis 障害等で fetchProgress が失敗してもポーリング本体は継続される。
 */
export function useAsyncTaskPage<TResult>({
  loadCache,
  checkStatus,
  fetchProgress,
}: UseAsyncTaskPageOptions<TResult>): UseAsyncTaskPageReturn<TResult> {
  const [phase, setPhase] = useState<AsyncTaskPhase>("loading-cache");
  const [result, setResult] = useState<TResult | null>(null);
  const [error, setError] = useState<AppErrorState | null>(null);
  const [progress, setProgress] = useState<TaskProgress | null>(null);

  /**
   * checkStatus を、進捗取得を並走させるラッパーに差し替える。
   * - ステータス取得と進捗取得は Promise.allSettled で並走
   * - 進捗取得失敗は無視し、ステータス取得失敗のみ呼び出し元に伝播する
   */
  const checkStatusWithProgress = useCallback(async () => {
    const [statusResult, progressResult] = await Promise.allSettled([
      checkStatus(),
      fetchProgress != null ? fetchProgress() : Promise.resolve(null),
    ]);

    if (progressResult.status === "fulfilled" && progressResult.value !== null) {
      setProgress(progressResult.value);
    }

    if (statusResult.status === "rejected") {
      throw statusResult.reason;
    }
    return statusResult.value;
  }, [checkStatus, fetchProgress]);

  const { startPolling, isPolling } = useTaskPolling({
    checkStatus: checkStatusWithProgress,
    onCompleted: async () => {
      try {
        const cached = await loadCache();
        if (cached.result) {
          setResult(cached.result);
          setPhase("result");
        } else {
          setPhase("input");
        }
      } catch {
        setPhase("input");
      }
    },
    onFailed: (err) => {
      setError(err);
      setPhase("input");
    },
    intervalMs: POLLING_CONFIG.initialInterval,
    maxIntervalMs: POLLING_CONFIG.maxInterval,
    multiplier: POLLING_CONFIG.multiplier,
  });

  /** 初回マウント時にキャッシュを読み込み、フェーズを決定する */
  useEffect(() => {
    let cancelled = false;

    loadCache()
      .then((cached) => {
        if (cancelled) return;
        if (isInProgressStatus(cached.status)) {
          setPhase("polling");
          return;
        }
        if (cached.result) {
          setResult(cached.result);
          setPhase("result");
        } else {
          setPhase("input");
        }
      })
      .catch(() => {
        if (!cancelled) setPhase("input");
      });

    return () => {
      cancelled = true;
    };
    // 初回マウント時のみ実行するため依存配列は空にする
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /** polling フェーズになったらポーリングを開始する */
  useEffect(() => {
    if (phase === "polling" && !isPolling) {
      startPolling();
    }
  }, [phase, isPolling, startPolling]);

  /** polling フェーズへ遷移するハンドラ */
  const transitionToPolling = () => {
    setPhase("polling");
  };

  /** 入力フェーズへ戻るハンドラ */
  const backToInput = () => {
    setPhase("input");
    setResult(null);
    setProgress(null);
  };

  return {
    phase,
    setPhase,
    result,
    setResult,
    error,
    setError,
    startPolling,
    isPolling,
    transitionToPolling,
    backToInput,
    progress,
  };
}
