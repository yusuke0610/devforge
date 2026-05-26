import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import formCacheReducer, { setCache } from "../store/formCacheSlice";
import { useDocumentForm, type UseDocumentFormOptions } from "./useDocumentForm";
import { ApiError } from "../utils/appError";

/** テスト用の Redux Store を生成するヘルパー */
function createTestStore() {
  return configureStore({
    reducer: { formCache: formCacheReducer },
  });
}

/** テスト用のフォーム状態型 */
type TestForm = { title: string };

/** テスト用のペイロード型 */
type TestPayload = { title: string };

/** テスト用のレスポンス型 */
type TestResponse = { id: string; title: string };

/** Provider ラッパーを生成するヘルパー */
function makeWrapper(store: ReturnType<typeof createTestStore>) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(Provider, { store, children });
  };
}

describe("useDocumentForm", () => {
  const mockLoadLatest = vi.fn();
  const mockCreateDocument = vi.fn();
  const mockUpdateDocument = vi.fn();
  const mockBuildPayload = vi.fn();
  const mockMapResponseToForm = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockBuildPayload.mockImplementation((form: TestForm) => ({ title: form.title }));
    mockMapResponseToForm.mockImplementation((r: TestResponse): TestForm => ({
      title: r.title,
    }));
  });

  /**
   * テスト共通の setup 関数。各 it では `overrides` で差分だけ指定する。
   * 5 箇所でコピペされていた renderHook + props の標準セットを集約する。
   */
  function setup(
    overrides: Partial<UseDocumentFormOptions<TestForm, TestPayload, TestResponse>> = {},
    storeOverrides: { presetCache?: { form: TestForm; documentId: string | null } } = {},
  ) {
    const store = createTestStore();
    if (storeOverrides.presetCache) {
      store.dispatch(
        setCache({
          key: overrides.cacheKey ?? "career",
          form: storeOverrides.presetCache.form,
          documentId: storeOverrides.presetCache.documentId,
        }),
      );
    }
    const hook = renderHook(
      () =>
        useDocumentForm<TestForm, TestPayload, TestResponse>({
          createInitialForm: () => ({ title: "" }),
          loadLatest: mockLoadLatest,
          createDocument: mockCreateDocument,
          updateDocument: mockUpdateDocument,
          buildPayload: mockBuildPayload,
          mapResponseToForm: mockMapResponseToForm,
          successMessage: "保存しました",
          ...overrides,
        }),
      { wrapper: makeWrapper(store) },
    );
    return { ...hook, store };
  }

  /** save() が API エラー（500）を返した場合、error メッセージが表示されること */
  it("save() で API エラーが発生した場合 error がセットされる", async () => {
    mockLoadLatest.mockRejectedValue(new Error("Not found"));
    const { result } = setup();

    // ローディング完了を待つ
    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // createDocument が 500 エラーを返すように設定
    mockCreateDocument.mockRejectedValueOnce(new Error("サーバーエラーが発生しました"));

    await act(async () => {
      await result.current.save();
    });

    expect(result.current.error).toBe("サーバーエラーが発生しました");
    expect(result.current.success).toBeNull();
  });

  /** save() が成功した場合、success メッセージが表示されること */
  it("save() が成功した場合 success がセットされる", async () => {
    mockLoadLatest.mockRejectedValue(new Error("Not found"));
    mockCreateDocument.mockResolvedValueOnce({ id: "new-id", title: "テスト" });

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.save();
    });

    expect(result.current.success).toBe("保存しました");
    expect(result.current.error).toBeNull();
  });

  /** save() が 401 ApiError を受け取った場合、error メッセージがセットされること */
  it("save() で 401 ApiError が発生した場合 error メッセージがセットされる", async () => {
    mockLoadLatest.mockRejectedValue(new Error("Not found"));
    mockCreateDocument.mockRejectedValueOnce(
      new ApiError({ code: "UNAUTHORIZED", message: "認証が必要です" }),
    );

    const { result } = setup();

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.save();
    });

    expect(result.current.error).toBe("認証が必要です");
    expect(result.current.success).toBeNull();
  });

  /**
   * Redux キャッシュにデータがある場合、loadLatest を呼ばずに
   * キャッシュ値を初期 form として使うこと。
   * ページ遷移で戻ってきたときの再 fetch チラつき/二重 API 呼び出しを直接守るテスト。
   */
  it("Redux キャッシュ存在時は loadLatest を呼ばずキャッシュ値を form の初期値にする", async () => {
    const { result } = setup(
      { cacheKey: "career" },
      { presetCache: { form: { title: "cached title" }, documentId: "doc-cached" } },
    );

    // キャッシュがあるので最初から loading=false
    expect(result.current.loading).toBe(false);
    // loadLatest は呼ばれない（二重 fetch 防止）
    expect(mockLoadLatest).not.toHaveBeenCalled();
    // キャッシュ値が form の初期値になる
    expect(result.current.form).toEqual({ title: "cached title" });
    expect(result.current.documentId).toBe("doc-cached");
  });

  /** beforeSave でエラーがスローされた場合、API が呼ばれずエラーが表示されること */
  it("beforeSave でエラーがスローされた場合 API が呼ばれずエラーがセットされる", async () => {
    mockLoadLatest.mockRejectedValue(new Error("Not found"));
    const { result } = setup({
      beforeSave: async () => {
        throw new Error("基本情報が未入力です");
      },
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      await result.current.save();
    });

    expect(result.current.error).toBe("基本情報が未入力です");
    expect(mockCreateDocument).not.toHaveBeenCalled();
  });
});
