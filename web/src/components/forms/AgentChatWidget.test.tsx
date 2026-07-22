import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AGENT_MESSAGES } from "../../constants/messages";
import { createInitialCareerForm } from "../../formMappers";
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

function renderWidget() {
  render(
    <ToastProvider>
      <AgentChatWidget
        form={createInitialCareerForm()}
        onApply={vi.fn()}
        isAuthenticated={true}
        requestLogin={vi.fn()}
      />
    </ToastProvider>,
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
  it("依頼文を入力して送信すると send が呼ばれる", async () => {
    renderWidget();

    openAndSend("自己PRを改善して");

    await waitFor(() => expect(sendMock).toHaveBeenCalledTimes(1));
    // send(form, scope, target, text) の順で依頼文が渡る（モデルは Haiku 固定 / ADR-0023）
    const call = sendMock.mock.calls[0];
    expect(call[3]).toBe("自己PRを改善して");
  });
});
