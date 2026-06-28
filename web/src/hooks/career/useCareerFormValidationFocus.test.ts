import { act, renderHook } from "@testing-library/react";
import type { FormEvent } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { buildSampleCareerForm } from "../../test/factories/careerForm";
import { useCareerFormValidationFocus } from "./useCareerFormValidationFocus";

const validateCareerFormMock = vi.fn();

vi.mock("../../payloadBuilders", () => ({
  validateCareerForm: (...args: unknown[]) => validateCareerFormMock(...args),
}));

/** preventDefault だけ持つ最小の submit イベント。 */
const submitEvent = () => ({ preventDefault: vi.fn() }) as unknown as FormEvent;

type Overrides = Partial<Parameters<typeof useCareerFormValidationFocus>[0]>;

function setup(overrides: Overrides = {}) {
  const params = {
    form: buildSampleCareerForm(),
    setForm: vi.fn(),
    isAuthenticated: true,
    changeCount: 0,
    save: vi.fn(),
    openSaveConfirm: vi.fn(),
    requestLogin: vi.fn(),
    persistDraft: vi.fn(),
    openMarkdownField: vi.fn(),
    ...overrides,
  };
  const view = renderHook((p: typeof params) => useCareerFormValidationFocus(p), {
    initialProps: params,
  });
  return { view, params };
}

beforeEach(() => {
  validateCareerFormMock.mockReset();
});

describe("useCareerFormValidationFocus", () => {
  it("未ログインで氏名が空なら、ログイン導線へ流さずバリデーションを表示する", () => {
    validateCareerFormMock.mockReturnValue({
      message: "氏名を入力してください",
      locator: { kind: "full_name" },
    });
    const { view, params } = setup({
      isAuthenticated: false,
      form: buildSampleCareerForm({ full_name: "  " }),
    });

    act(() => view.result.current.onSubmit(submitEvent()));

    expect(params.requestLogin).not.toHaveBeenCalled();
    expect(view.result.current.validationError).toBe("氏名を入力してください");
  });

  it("未ログインで氏名があれば、保存せずログイン導線へ流す", () => {
    const { view, params } = setup({
      isAuthenticated: false,
      form: buildSampleCareerForm({ full_name: "山田 太郎" }),
    });

    act(() => view.result.current.onSubmit(submitEvent()));

    expect(params.requestLogin).toHaveBeenCalledTimes(1);
    expect(params.save).not.toHaveBeenCalled();
    expect(view.result.current.validationError).toBeNull();
  });

  it("未ログインのログイン遷移前に、現在のフォームを同期退避してから requestLogin する", () => {
    const form = buildSampleCareerForm({ full_name: "山田 太郎" });
    const { view, params } = setup({ isAuthenticated: false, form });

    act(() => view.result.current.onSubmit(submitEvent()));

    // 最新フォームを退避してからログイン導線へ（取りこぼし防止）
    expect(params.persistDraft).toHaveBeenCalledWith(form);
    const persistOrder = (params.persistDraft as ReturnType<typeof vi.fn>).mock
      .invocationCallOrder[0];
    const loginOrder = (params.requestLogin as ReturnType<typeof vi.fn>).mock
      .invocationCallOrder[0];
    expect(persistOrder).toBeLessThan(loginOrder);
  });

  it("自己PR / 職務要約の失敗時は該当 Markdown モーダルを自動で開く", () => {
    validateCareerFormMock.mockReturnValue({
      message: "職務要約を入力してください",
      locator: { kind: "career_summary" },
    });
    const { view, params } = setup({ isAuthenticated: true });

    act(() => view.result.current.onSubmit(submitEvent()));

    expect(params.openMarkdownField).toHaveBeenCalledWith("career_summary");
    expect(view.result.current.focusLocator).toEqual({ kind: "career_summary" });
    expect(view.result.current.validationError).toBe("職務要約を入力してください");
  });

  it("検証 OK かつ変更なしなら確認を挟まず直接保存する", () => {
    validateCareerFormMock.mockReturnValue(null);
    const { view, params } = setup({ isAuthenticated: true, changeCount: 0 });

    act(() => view.result.current.onSubmit(submitEvent()));

    expect(params.save).toHaveBeenCalledTimes(1);
    expect(params.openSaveConfirm).not.toHaveBeenCalled();
  });

  it("検証 OK かつ変更ありなら保存確認モーダルを開く", () => {
    validateCareerFormMock.mockReturnValue(null);
    const { view, params } = setup({ isAuthenticated: true, changeCount: 2 });

    act(() => view.result.current.onSubmit(submitEvent()));

    expect(params.openSaveConfirm).toHaveBeenCalledTimes(1);
    expect(params.save).not.toHaveBeenCalled();
  });

  it("フィールド編集でフォーカス強調（赤枠）とエラー表示が解除される", () => {
    validateCareerFormMock.mockReturnValue({
      message: "職務要約を入力してください",
      locator: { kind: "career_summary" },
    });
    const { view } = setup({ isAuthenticated: true });

    act(() => view.result.current.onSubmit(submitEvent()));
    expect(view.result.current.focusLocator).not.toBeNull();

    act(() => view.result.current.onChangeField("career_summary", "改善後の要約"));

    expect(view.result.current.focusLocator).toBeNull();
    expect(view.result.current.validationError).toBeNull();
  });
});
