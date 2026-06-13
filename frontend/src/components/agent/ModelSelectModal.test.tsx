import { configureStore } from "@reduxjs/toolkit";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { Provider } from "react-redux";
import { beforeEach, describe, expect, it, vi } from "vitest";

import agentModelReducer from "../../store/agentModelSlice";
import {
  CreditBalanceContext,
  type CreditBalanceContextValue,
} from "../billing/creditBalanceContext";
import { ModelSelectModal } from "./ModelSelectModal";

const getAgentUsageSummaryMock = vi.fn();

vi.mock("../../api/billing", () => ({
  getAgentUsageSummary: (...args: unknown[]) => getAgentUsageSummaryMock(...args),
}));

type Store = ReturnType<typeof makeStore>;

function makeStore(model: "haiku" | "sonnet" = "haiku") {
  return configureStore({
    reducer: { agentModel: agentModelReducer },
    preloadedState: { agentModel: { model } },
  });
}

function renderModal(opts: {
  store?: Store;
  balance?: number | null;
  onClose?: () => void;
  usage?: { model: string; chat_count: number; input_tokens: number; output_tokens: number; credit_cost: number }[];
}) {
  getAgentUsageSummaryMock.mockResolvedValue(opts.usage ?? []);
  const store = opts.store ?? makeStore();
  const balanceValue: CreditBalanceContextValue = {
    balance: opts.balance ?? null,
    loading: false,
    error: null,
    refresh: vi.fn(),
  };
  const wrapper = (ui: ReactNode) => (
    <Provider store={store}>
      <CreditBalanceContext.Provider value={balanceValue}>{ui}</CreditBalanceContext.Provider>
    </Provider>
  );
  render(wrapper(<ModelSelectModal onClose={opts.onClose ?? vi.fn()} />));
  return store;
}

beforeEach(() => {
  getAgentUsageSummaryMock.mockReset();
  getAgentUsageSummaryMock.mockResolvedValue([]);
});

describe("ModelSelectModal", () => {
  it("Haiku / Sonnet のカードが表示される", () => {
    renderModal({});
    expect(screen.getByRole("button", { name: /^Haiku/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Sonnet/ })).toBeTruthy();
  });

  it("現在選択中のモデルカードに『選択中』が付く", () => {
    renderModal({ store: makeStore("sonnet") });
    const sonnetCard = screen.getByRole("button", { name: /^Sonnet/ });
    expect(within(sonnetCard).getByText("選択中")).toBeTruthy();
  });

  it("カードを押すとグローバル設定が切り替わり、モーダルが閉じる", () => {
    const onClose = vi.fn();
    const store = renderModal({ onClose });

    fireEvent.click(screen.getByRole("button", { name: /^Sonnet/ }));

    expect(store.getState().agentModel.model).toBe("sonnet");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("残高 0 で Sonnet カードに残高不足の警告を出す（選択自体は許可）", () => {
    renderModal({ balance: 0 });
    const sonnetCard = screen.getByRole("button", { name: /^Sonnet/ });
    expect(within(sonnetCard).getByText(/残高が不足/)).toBeTruthy();
    // 無料カードには警告を出さない
    const haikuCard = screen.getByRole("button", { name: /^Haiku/ });
    expect(within(haikuCard).queryByText(/残高が不足/)).toBeNull();
  });

  it("残高が十分なら Sonnet カードに警告を出さない", () => {
    renderModal({ balance: 5000 });
    const sonnetCard = screen.getByRole("button", { name: /^Sonnet/ });
    expect(within(sonnetCard).queryByText(/残高が不足/)).toBeNull();
  });

  it("利用実績があるとカードに利用回数・消費クレジットと残回数目安を表示する", async () => {
    renderModal({
      balance: 2700,
      usage: [
        { model: "sonnet", chat_count: 4, input_tokens: 4000, output_tokens: 4000, credit_cost: 1080 },
      ],
    });

    const sonnetCard = screen.getByRole("button", { name: /^Sonnet/ });
    // これまで 4 回・約 1,080 クレジット消費
    await waitFor(() => {
      expect(within(sonnetCard).getByText(/これまで 4 回/)).toBeTruthy();
    });
    // 平均 270/回・残高 2700 → あと約 10 回
    expect(within(sonnetCard).getByText(/あと約 10 回/)).toBeTruthy();
  });

  it("利用実績が無いカードは『まだ利用していません』を表示する", async () => {
    renderModal({ balance: 1000 });
    const haikuCard = screen.getByRole("button", { name: /^Haiku/ });
    await waitFor(() => {
      expect(within(haikuCard).getByText("まだ利用していません")).toBeTruthy();
    });
  });
});
