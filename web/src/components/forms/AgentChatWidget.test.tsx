import { configureStore } from "@reduxjs/toolkit";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentModelAlias } from "../../api/types";
import { AGENT_MESSAGES } from "../../constants/messages";
import { createInitialCareerForm } from "../../formMappers";
import agentModelReducer from "../../store/agentModelSlice";
import formCacheReducer from "../../store/formCacheSlice";
import { ToastProvider } from "../ui/toast";
import { AgentChatWidget } from "./AgentChatWidget";

// useAgentChat はネットワークを伴うため send をモックし、ウィジェットの送信配線を検証する。
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
  render(
    <Provider store={makeStore(model)}>
      <ToastProvider>
        <AgentChatWidget
          form={createInitialCareerForm()}
          onApply={vi.fn()}
          isAuthenticated={true}
          requestLogin={vi.fn()}
        />
      </ToastProvider>
    </Provider>,
  );
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

describe("AgentChatWidget の送信", () => {
  it("依頼文を入力して送信すると選択中モデルで send が呼ばれる", async () => {
    renderWidget("haiku");

    openAndSend("自己PRを改善して");

    await waitFor(() => expect(sendMock).toHaveBeenCalledTimes(1));
    // send(form, scope, target, text, model) の順で選択中モデルが渡る
    const call = sendMock.mock.calls[0];
    expect(call[3]).toBe("自己PRを改善して");
    expect(call[4]).toBe("haiku");
  });
});
