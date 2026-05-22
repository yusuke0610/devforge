import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

/** フォームキャッシュのキー。各フォームページに対応。 */
export type FormCacheKey = "career";

interface FormCacheEntry {
  /** フォーム状態（型は各フォームに依存するため unknown） */
  form: unknown;
  /**
   * サーバの最新スナップショット（dirty 判定の基準値）。
   * loadLatest 成功時 / save 成功時にのみ更新する。
   * 未ロード状態（load 前）は null。
   */
  baseline: unknown;
  /** 保存済みドキュメント ID（未保存なら null） */
  documentId: string | null;
}

type FormCacheState = Record<string, FormCacheEntry | undefined>;

const formCacheSlice = createSlice({
  name: "formCache",
  initialState: {} as FormCacheState,
  reducers: {
    setCache(
      state,
      action: PayloadAction<{
        key: FormCacheKey;
        form: unknown;
        documentId: string | null;
      }>,
    ) {
      const { key, form, documentId } = action.payload;
      const prevBaseline = state[key]?.baseline ?? null;
      state[key] = { form, baseline: prevBaseline, documentId };
    },
    /** baseline を更新する。サーバ同期（load / save）成功時のみ呼ぶこと。 */
    setBaseline(
      state,
      action: PayloadAction<{
        key: FormCacheKey;
        baseline: unknown;
      }>,
    ) {
      const { key, baseline } = action.payload;
      const existing = state[key];
      if (existing) {
        existing.baseline = baseline;
      } else {
        state[key] = { form: baseline, baseline, documentId: null };
      }
    },
    clearCache(state, action: PayloadAction<FormCacheKey>) {
      delete state[action.payload];
    },
  },
});

export const { setCache, setBaseline, clearCache } = formCacheSlice.actions;
export default formCacheSlice.reducer;
