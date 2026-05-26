import type { ErrorCodeKey } from "./errorCodes";

type RecoveryAction = {
  label: string;
  fn: (() => void) | null;
};

/**
 * エラーコード → メッセージ + 回復アクションのマップ。
 *
 * キーは `frontend/src/constants/errorCodes.ts` の `ErrorCodeKey` で型縛り。
 * backend `backend/app/core/errors.py:ErrorCode` に新しいコードを追加した場合、
 * ERROR_CODES と本マップの両方に同時追加が必要（型エラーで漏れを検出）。
 */
export const ERROR_CONFIG: Record<
  ErrorCodeKey,
  {
    message: string;
    recovery: RecoveryAction | null;
  }
> = {
  AUTH_EXPIRED: {
    message: "セッションが切れました",
    recovery: { label: "ログインし直す", fn: () => window.location.assign("/login") },
  },
  AUTH_REQUIRED: {
    message: "認証が必要です",
    recovery: { label: "ログインし直す", fn: () => window.location.assign("/login") },
  },
  GITHUB_RATE_LIMITED: {
    message: "GitHub API の制限に達しました（1時間あたりの上限）",
    recovery: { label: "後で再試行", fn: null },
  },
  GITHUB_USER_NOT_FOUND: {
    message: "GitHub ユーザーが見つかりません",
    recovery: { label: "ユーザー名を見直す", fn: null },
  },
  LLM_TIMEOUT: {
    message: "AI 分析がタイムアウトしました",
    recovery: { label: "再分析する", fn: null },
  },
  LLM_UNAVAILABLE: {
    message: "AI 分析サービスが一時的に利用できません",
    recovery: { label: "後で再試行", fn: null },
  },
  QIITA_RATE_LIMITED: {
    message: "Qiita API の制限に達しました",
    recovery: { label: "1時間後に再試行", fn: null },
  },
  RATE_LIMITED: {
    message: "リクエストが集中しています",
    recovery: { label: "少し待って再試行", fn: null },
  },
  VALIDATION_ERROR: {
    message: "入力内容を確認してください",
    recovery: null,
  },
  INTERNAL_ERROR: {
    message: "予期しないエラーが発生しました",
    recovery: { label: "ページを再読み込み", fn: () => window.location.reload() },
  },
};
