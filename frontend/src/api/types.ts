/**
 * OpenAPI 生成型（`generated.ts`）を backend のクラス名のまま 1:1 で再エクスポートする薄い層。
 *
 * 呼び出し側は `components["schemas"][...]` を直書きせず、ここで定義した再エクスポート名を import する。
 * これは FE 独自名ではなく生成物の機械的ミラーであり、二重管理にはならない（ADR-0007）。
 * backend の Pydantic schema が DTO の Single Source of Truth。型を増やす場合はここに 1 行追加する。
 */
import type { components } from "./generated";

/**
 * 非同期タスクのステータスを返す軽量レスポンス。
 * backend `app/schemas/shared.py:TaskStatusResponse` のミラー。
 */
export type TaskStatusResponse = components["schemas"]["TaskStatusResponse"];
