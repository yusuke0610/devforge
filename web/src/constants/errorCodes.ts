/**
 * バックエンドが返すエラーコードの SSoT 型定義。
 *
 * ## 同期ルール
 *
 * 本ファイルは backend の `backend/app/core/errors.py:ErrorCode` enum と
 * 完全に同じキー集合を保つ必要がある。
 *
 * - BE で新しい ErrorCode を追加 → 本ファイルにもキーを追加し、
 *   `frontend/src/constants/errorMessages.ts` の `ERROR_CONFIG` にメッセージと recovery を追加すること
 * - キー名・値の rename も両側を同時に変更すること
 *
 * 型システム上は `ERROR_CONFIG` を `Record<ErrorCodeKey, ...>` で縛ることで、
 * キーの網羅漏れを TypeScript の型エラーとして検出できる。
 *
 * 関連: `backend/app/core/errors.py`, `frontend/src/utils/appError.ts`
 */

export const ERROR_CODES = [
  // 認証
  "AUTH_EXPIRED",
  "AUTH_REQUIRED",
  // GitHub
  "GITHUB_RATE_LIMITED",
  "GITHUB_USER_NOT_FOUND",
  // バリデーション
  "VALIDATION_ERROR",
  // 外部 API
  "QIITA_RATE_LIMITED",
  // Agent（LLM チャット / ADR-0010）
  "AGENT_LLM_ERROR",
  "AGENT_PARSE_ERROR",
  // Agent の日次利用上限（#521 / ADR-0023）
  "AGENT_DAILY_LIMIT_EXCEEDED",
  // 課金（プリペイドクレジット / ADR-0012）
  "INSUFFICIENT_CREDITS",
  // 決済（Stripe Checkout / ADR-0012 Phase 2）
  "PAYMENT_ERROR",
  // アプリケーション全体
  "RATE_LIMITED",
  // サーバー
  "INTERNAL_ERROR",
] as const;

export type ErrorCodeKey = (typeof ERROR_CODES)[number];

export function isErrorCode(value: unknown): value is ErrorCodeKey {
  return typeof value === "string" && (ERROR_CODES as readonly string[]).includes(value);
}
