import { configureStore } from "@reduxjs/toolkit";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentModelAlias } from "../../api/types";
import { AGENT_MESSAGES } from "../../constants/messages";
import { createInitialCareerForm } from "../../formMappers";
import agentModelReducer from "../../store/agentModelSlice";
import formCacheReducer from "../../store/formCacheSlice";
import {
  CreditBalanceContext,
  type CreditBalanceContextValue,
} from "../billing/creditBalanceContext";
import { ToastProvider } from "../ui/toast";
import { AgentChatWidget } from "./AgentChatWidget";

// useAgentChat はネットワークを伴うため send をモックし、ウィジェット側の
// 「有料モデルなら送信後に残高を再取得する」配線だけを検証対象にする。
const { sendMock } = vi.hoisted(() => ({ sendMock: vi.fn() }));
vi.mock("../../hooks/career/useAgentChat", () => ({
  useAgentChat: () => ({
    entries: [],
    sending: false,
    error: null,
    send: sendMock,
    markApplied: vi.fn(),
    clearError: vi.fn(),
  }),
}));

function makeStore(model: AgentModelAlias) {
  return configureStore({
    reducer: { agentModel: agentModelReducer, formCache: formCacheReducer },
    preloadedState: { agentModel: { model } },
  });
}

function renderWidget(model: AgentModelAlias) {
  const refresh = vi.fn().mockResolvedValue(undefined);
  const balanceValue: CreditBalanceContextValue = {
    balance: 1000,
    loading: false,
    error: null,
    refresh,
  };
  render(
    <Provider store={makeStore(model)}>
      <CreditBalanceContext.Provider value={balanceValue}>
        <ToastProvider>
          <AgentChatWidget
            form={createInitialCareerForm()}
            onApply={vi.fn()}
            isAuthenticated={true}
            requestLogin={vi.fn()}
          />
        </ToastProvider>
      </CreditBalanceContext.Provider>
    </Provider>,
  );
  return { refresh };
}

/** パネルを開いて依頼文を入力し、送信ボタンを押すまでの操作。 */
function openAndSend(text: string) {
  fireEvent.click(screen.getByRole("button", { name: AGENT_MESSAGES.OPEN_LABEL }));
  fireEvent.change(screen.getByPlaceholderText(AGENT_MESSAGES.PROMPT_PLACEHOLDER), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole("button", { name: AGENT_MESSAGES.SEND }));
}

beforeEach(() => {
  sendMock.mockReset();
  sendMock.mockResolvedValue(undefined);
});

describe("AgentChatWidget の残高再取得", () => {
  it("有料モデル（gemini-pro）で送信すると送信後に残高を再取得する", async () => {
    const { refresh } = renderWidget("gemini-pro");

    openAndSend("自己PRを改善して");

    await waitFor(() => expect(sendMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  });

  it("有料モデル（gpt）でも送信後に残高を再取得する", async () => {
    const { refresh } = renderWidget("gpt");

    openAndSend("職務要約を整えて");

    await waitFor(() => expect(sendMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  });

  it("無料モデル（haiku）では残高を再取得しない", async () => {
    const { refresh } = renderWidget("haiku");

    openAndSend("自己PRを改善して");

    await waitFor(() => expect(sendMock).toHaveBeenCalledTimes(1));
    expect(refresh).not.toHaveBeenCalled();
  });
});
