import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import { configureStore } from "@reduxjs/toolkit";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { CareerResumeForm } from "./CareerResumeForm";
import { LoginPromptContext } from "../auth/loginPromptContext";
import { ToastProvider } from "../ui/toast";
import formCacheReducer from "../../store/formCacheSlice";
import { UI_MESSAGES, VALIDATION_MESSAGES } from "../../constants/messages";

// 原本ビューは react-pdf / pdf.js を遅延ロードするため、フォームの単体テストではスタブに差し替える。
vi.mock("./ResumeSourceTracePanel", () => ({
  ResumeSourceTracePanel: () => <div data-testid="source-panel-stub" />,
}));

// マスタデータ取得は実 fetch を避けて空配列を返す（匿名分岐の検証には不要なため）。
vi.mock("../../api/master-data", () => ({
  getQualifications: vi.fn().mockResolvedValue([]),
  getTechnologyStacks: vi.fn().mockResolvedValue([]),
}));

/** formCache だけを持つ最小ストアを作る。 */
function makeStore() {
  return configureStore({ reducer: { formCache: formCacheReducer } });
}

/** 未ログイン状態の CareerResumeForm を描画し、requestLogin スパイを返す。 */
function renderAnonymousForm() {
  const requestLogin = vi.fn();
  render(
    <Provider store={makeStore()}>
      <LoginPromptContext.Provider value={requestLogin}>
        <ToastProvider>
          <CareerResumeForm isAuthenticated={false} />
        </ToastProvider>
      </LoginPromptContext.Provider>
    </Provider>,
  );
  return { requestLogin };
}

describe("CareerResumeForm（未ログインの保存導線）", () => {
  beforeEach(() => {
    // ドラフト退避（sessionStorage）がテスト間で漏れないようにする。
    window.sessionStorage.clear();
  });

  /** 保存ボタンはマスタデータ取得が終わるまで非活性なので、活性化を待ってから返す。 */
  async function waitForEnabledSaveButton(): Promise<HTMLElement> {
    const button = screen.getByRole("button", { name: UI_MESSAGES.FORM_SAVE });
    await waitFor(() => expect(button).toBeEnabled());
    return button;
  }

  it("氏名が空のまま保存すると、ログインを促さず氏名必須エラーを表示する", async () => {
    const { requestLogin } = renderAnonymousForm();

    fireEvent.click(await waitForEnabledSaveButton());

    expect(screen.getByText(VALIDATION_MESSAGES.FULL_NAME_REQUIRED)).toBeInTheDocument();
    expect(requestLogin).not.toHaveBeenCalled();
  });

  it("氏名を入力して保存すると、バリデーションを通してログイン促進を呼ぶ", async () => {
    const { requestLogin } = renderAnonymousForm();

    const saveButton = await waitForEnabledSaveButton();
    // 氏名入力はプレースホルダ文言ではなくラベル（ロール + アクセシブル名）で特定する。
    fireEvent.change(screen.getByRole("textbox", { name: /氏名/ }), {
      target: { value: "山田 太郎" },
    });
    fireEvent.click(saveButton);

    expect(requestLogin).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(VALIDATION_MESSAGES.FULL_NAME_REQUIRED)).not.toBeInTheDocument();
  });
});
