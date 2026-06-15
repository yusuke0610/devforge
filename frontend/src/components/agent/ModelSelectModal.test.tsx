import { configureStore } from "@reduxjs/toolkit";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { Provider } from "react-redux";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AGENT_MODEL_OPTIONS, CREDIT_ESTIMATE_REFERENCE } from "../../constants/agentModels";
import {
  AGENT_MODEL_MESSAGES,
  creditsForChatsLabel,
  modelUsageLabel,
} from "../../constants/messages";
import agentModelReducer from "../../store/agentModelSlice";
import {
  CreditBalanceContext,
  type CreditBalanceContextValue,
} from "../billing/creditBalanceContext";
import { ModelSelectModal } from "./ModelSelectModal";

// 表示文言は SSoT（constants/messages・agentModels）から引き、テストとメッセージ正本の乖離を防ぐ。
const HAIKU_NAME = AGENT_MODEL_OPTIONS.find((option) => option.alias === "haiku")!.name;
const SONNET_NAME = AGENT_MODEL_OPTIONS.find((option) => option.alias === "sonnet")!.name;
const haikuNamePattern = new RegExp(`^${HAIKU_NAME}`);
const sonnetNamePattern = new RegExp(`^${SONNET_NAME}`);

const getAgentUsageSummaryMock = vi.fn();
const getModelRatesMock = vi.fn();

vi.mock("../../api/billing", () => ({
  getAgentUsageSummary: (...args: unknown[]) => getAgentUsageSummaryMock(...args),
  getModelRates: (...args: unknown[]) => getModelRatesMock(...args),
}));

const DEFAULT_RATES = [
  { model: "haiku", is_free: true, baseline_credits_per_chat: 0 },
  { model: "sonnet", is_free: false, baseline_credits_per_chat: 12 },
];

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
  getModelRatesMock.mockResolvedValue(DEFAULT_RATES);
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
  getModelRatesMock.mockReset();
  getModelRatesMock.mockResolvedValue(DEFAULT_RATES);
});

describe("ModelSelectModal", () => {
  it("Haiku / Sonnet のカードが表示される", () => {
    renderModal({});
    expect(screen.getByRole("button", { name: haikuNamePattern })).toBeTruthy();
    expect(screen.getByRole("button", { name: sonnetNamePattern })).toBeTruthy();
  });

  it("現在選択中のモデルカードに『選択中』が付く", () => {
    renderModal({ store: makeStore("sonnet") });
    const sonnetCard = screen.getByRole("button", { name: sonnetNamePattern });
    expect(within(sonnetCard).getByText(AGENT_MODEL_MESSAGES.CURRENT_BADGE)).toBeTruthy();
  });

  it("カードを押すとグローバル設定が切り替わり、モーダルが閉じる", () => {
    const onClose = vi.fn();
    const store = renderModal({ onClose });

    fireEvent.click(screen.getByRole("button", { name: sonnetNamePattern }));

    expect(store.getState().agentModel.model).toBe("sonnet");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("残高 0 で Sonnet カードに残高不足の警告を出す（選択自体は許可）", () => {
    renderModal({ balance: 0 });
    const sonnetCard = screen.getByRole("button", { name: sonnetNamePattern });
    expect(within(sonnetCard).getByText(AGENT_MODEL_MESSAGES.INSUFFICIENT_HINT)).toBeTruthy();
    // 無料カードには警告を出さない
    const haikuCard = screen.getByRole("button", { name: haikuNamePattern });
    expect(within(haikuCard).queryByText(AGENT_MODEL_MESSAGES.INSUFFICIENT_HINT)).toBeNull();
  });

  it("残高が十分なら Sonnet カードに警告を出さない", () => {
    renderModal({ balance: 5000 });
    const sonnetCard = screen.getByRole("button", { name: sonnetNamePattern });
    expect(within(sonnetCard).queryByText(AGENT_MODEL_MESSAGES.INSUFFICIENT_HINT)).toBeNull();
  });

  it("残高未取得（null）の間は Sonnet カードに残高不足の警告を出さない", () => {
    renderModal({ balance: null });
    const sonnetCard = screen.getByRole("button", { name: sonnetNamePattern });
    expect(within(sonnetCard).queryByText(AGENT_MODEL_MESSAGES.INSUFFICIENT_HINT)).toBeNull();
  });

  it("利用実績があると実測平均から『1,000クレジットで平均N回』を表示する", async () => {
    renderModal({
      balance: 2700,
      usage: [
        { model: "sonnet", chat_count: 4, input_tokens: 4000, output_tokens: 4000, credit_cost: 20 },
      ],
    });

    const sonnetCard = screen.getByRole("button", { name: sonnetNamePattern });
    // これまで 4 回・約 20 クレジット消費（実測平均 5/回）
    await waitFor(() => {
      expect(within(sonnetCard).getByText(modelUsageLabel(4, 20))).toBeTruthy();
    });
    // 平均 5/回 → 1,000 クレジットで平均 200 回（残高には依存しない）
    expect(
      within(sonnetCard).getByText(creditsForChatsLabel(CREDIT_ESTIMATE_REFERENCE, 200), {
        exact: false,
      }),
    ).toBeTruthy();
  });

  it("利用実績が無くてもベースラインレートで平均回数を出す", async () => {
    // usage 空・rates baseline sonnet=12 → 1,000 / 12 = 83
    renderModal({ balance: 1000 });
    const sonnetCard = screen.getByRole("button", { name: sonnetNamePattern });
    await waitFor(() => {
      expect(
        within(sonnetCard).getByText(creditsForChatsLabel(CREDIT_ESTIMATE_REFERENCE, 83), {
          exact: false,
        }),
      ).toBeTruthy();
    });
    // 利用実績のテキストは「まだ利用していません」
    expect(within(sonnetCard).getByText(AGENT_MODEL_MESSAGES.USAGE_NONE)).toBeTruthy();
  });

  it("無料モデル（Haiku）には回数目安を出さない", async () => {
    renderModal({ balance: 1000 });
    const haikuCard = screen.getByRole("button", { name: haikuNamePattern });
    await waitFor(() => {
      expect(within(haikuCard).getByText(AGENT_MODEL_MESSAGES.USAGE_NONE)).toBeTruthy();
    });
    expect(within(haikuCard).queryByText(/クレジットで平均/)).toBeNull();
  });
});
