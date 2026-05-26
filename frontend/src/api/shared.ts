/**
 * 複数ドメインで共用する API レスポンス型。
 *
 * backend の `app/schemas/shared.py` に対応する。
 */

/** 非同期タスクのステータスを返す軽量レスポンス。 */
export interface TaskStatusResponse {
  status: string;
  error_message?: string;
  error_code?: string;
  error_id?: string;
  retry_after?: number;
}
