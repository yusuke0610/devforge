import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

import type { TaskProgress } from "../api/intelligence";

/**
 * 職務経歴書 PDF インポートの進行フェーズ。
 * - idle: 未開始
 * - uploading: PDF をサーバーへアップロード中
 * - polling: 解析タスクの完了待ち（バックエンドで非同期実行）
 * - ready: 解析完了。プレビュー結果取得待ち（モーダル表示直前）
 * - error: アップロード or 解析が失敗
 */
export type ResumeImportPhase =
  | "idle"
  | "uploading"
  | "polling"
  | "ready"
  | "error";

/**
 * Redux に乗せる import 状態。
 *
 * 永続化（redux-persist）されるため、PII を含む値は格納しない。
 * 抽出された CareerResumePayload（氏名・経歴等）は本 slice に置かず、
 * `phase === "ready"` を検知したコンポーネント側で API から都度取得する。
 */
export interface ResumeImportState {
  /** バックエンドが発行した import 識別子（UUID） */
  importId: string | null;
  /** 進行フェーズ */
  phase: ResumeImportPhase;
  /** エラー情報（backend 由来の標準化メッセージのみ） */
  error: {
    code: string;
    message: string;
    action: string | null;
    retryAfter: number | null;
    errorId: string;
  } | null;
  /**
   * バックエンドのステップ進捗。
   * ポーリングごとに ResumeImportPoller が上書きする（Redis 障害時は null）。
   * 現在の UI（AsyncTaskLoading）では描画しないが、ポーラーの観測状態として保持する。
   */
  progress: TaskProgress | null;
}

const initialState: ResumeImportState = {
  importId: null,
  phase: "idle",
  error: null,
  progress: null,
};

const resumeImportSlice = createSlice({
  name: "resumeImport",
  initialState,
  reducers: {
    /** PDF アップロード開始時に呼ぶ。phase: "uploading" に遷移。 */
    beginUpload(state) {
      state.importId = null;
      state.phase = "uploading";
      state.error = null;
      state.progress = null;
    },
    /**
     * アップロード成功時に呼ぶ。
     * importId をセットして polling フェーズへ遷移する。
     */
    beginPolling(state, action: PayloadAction<{ importId: string }>) {
      state.importId = action.payload.importId;
      state.phase = "polling";
      state.error = null;
    },
    /**
     * 解析完了時に呼ぶ。phase: "ready" に遷移。
     * 結果データは Redux に乗せず、参照側が API から取得する。
     */
    markReady(state) {
      state.phase = "ready";
      state.error = null;
    },
    /** エラー発生時に呼ぶ。phase: "error" に遷移。 */
    setError(state, action: PayloadAction<ResumeImportState["error"]>) {
      state.phase = "error";
      state.error = action.payload;
    },
    /** ポーリングのたびに進捗を上書きする。 */
    setProgress(state, action: PayloadAction<TaskProgress | null>) {
      state.progress = action.payload;
    },
    /** import 状態を初期化する（モーダル確定 / キャンセル / リセット時） */
    clearImport() {
      return initialState;
    },
  },
});

export const {
  beginUpload,
  beginPolling,
  markReady,
  setError,
  setProgress,
  clearImport,
} = resumeImportSlice.actions;
export default resumeImportSlice.reducer;
