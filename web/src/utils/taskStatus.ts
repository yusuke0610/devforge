/**
 * 非同期タスクのステータス契約をフロント側で 1 か所に集約するモジュール。
 *
 * backend (``app/services/tasks/base.py``) と同じ判定式を採用する。
 * 文字列リテラルの直接比較を hook 内に散らさないことで、契約変更時の
 * 修正箇所を最小化する。
 */

/** バックエンドが返すタスクステータス文字列。 */
export type TaskStatus =
  | "pending"
  | "processing"
  | "retrying"
  | "completed"
  | "dead_letter";

/**
 * タスクが「進行中」（pending / processing / retrying）かを判定する。
 * UI 側ではポーリング継続や入力フォーム表示制御の判定に使う。
 */
export function isInProgressStatus(status: string | null | undefined): boolean {
  return status === "pending" || status === "processing" || status === "retrying";
}
