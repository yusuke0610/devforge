import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";

import { createInitialCareerForm } from "../../formMappers";
import type { CareerFormState } from "../../payloadBuilders";
import { loadCareerDraft, saveCareerDraft } from "../../utils/careerDraft";
import { useCareerDraftRestore } from "./useCareerDraftRestore";

/** テスト用ドラフト（氏名だけ埋めた最小フォーム） */
function draftForm(): CareerFormState {
  return { ...createInitialCareerForm(), full_name: "山田太郎" };
}

type Options = Parameters<typeof useCareerDraftRestore>[0];

function setup(overrides: Partial<Options>) {
  const setForm = vi.fn();
  const save = vi.fn<(form?: CareerFormState) => Promise<boolean>>().mockResolvedValue(true);
  const notifyRestored = vi.fn();
  const hook = renderHook((props: Options) => useCareerDraftRestore(props), {
    initialProps: {
      isAuthenticated: true,
      loading: false,
      documentId: null,
      setForm,
      save,
      notifyRestored,
      ...overrides,
    },
  });
  return { setForm, save, notifyRestored, hook };
}

describe("useCareerDraftRestore", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it("ドラフトが無ければ何もしない", () => {
    const { setForm, save, notifyRestored } = setup({});

    expect(save).not.toHaveBeenCalled();
    expect(setForm).not.toHaveBeenCalled();
    expect(notifyRestored).not.toHaveBeenCalled();
  });

  it("新規ユーザー（documentId=null）はドラフトを自動保存し、成功時に退避を破棄する", async () => {
    const draft = draftForm();
    saveCareerDraft(draft);

    const { save, setForm, notifyRestored } = setup({ documentId: null });

    await waitFor(() => {
      expect(save).toHaveBeenCalledWith(draft);
    });
    await waitFor(() => {
      expect(loadCareerDraft()).toBeNull();
    });
    // 新規保存パスでは復元通知も setForm も不要
    expect(notifyRestored).not.toHaveBeenCalled();
    expect(setForm).not.toHaveBeenCalled();
  });

  it("既存ユーザー（documentId あり）はフォームへ復元し通知する（自動保存しない）", async () => {
    const draft = draftForm();
    saveCareerDraft(draft);

    const { save, setForm, notifyRestored } = setup({ documentId: "existing-id" });

    await waitFor(() => {
      expect(setForm).toHaveBeenCalledWith(draft);
    });
    expect(notifyRestored).toHaveBeenCalledTimes(1);
    expect(save).not.toHaveBeenCalled();
    expect(loadCareerDraft()).toBeNull();
  });

  it("未ログインの間は何もしない", () => {
    saveCareerDraft(draftForm());
    const { save, setForm } = setup({ isAuthenticated: false });

    expect(save).not.toHaveBeenCalled();
    expect(setForm).not.toHaveBeenCalled();
    // ドラフトは温存される（ログイン後に処理する）
    expect(loadCareerDraft()).not.toBeNull();
  });

  it("ロード未確定（loading=true）の間は待機し、確定後に処理する", async () => {
    const draft = draftForm();
    saveCareerDraft(draft);

    const { save, hook } = setup({ loading: true, documentId: null });
    expect(save).not.toHaveBeenCalled();

    hook.rerender({
      isAuthenticated: true,
      loading: false,
      documentId: null,
      setForm: vi.fn(),
      save,
      notifyRestored: vi.fn(),
    });

    await waitFor(() => {
      expect(save).toHaveBeenCalledWith(draft);
    });
  });
});
