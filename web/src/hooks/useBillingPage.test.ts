import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useBillingPage } from "./useBillingPage";

const getCreditBalanceMock = vi.fn();
const getCreditPacksMock = vi.fn();
const getCreditTransactionsMock = vi.fn();
const getModelRatesMock = vi.fn();

vi.mock("../api/billing", () => ({
  getCreditBalance: () => getCreditBalanceMock(),
  getCreditPacks: () => getCreditPacksMock(),
  getCreditTransactions: () => getCreditTransactionsMock(),
  getModelRates: () => getModelRatesMock(),
}));

beforeEach(() => {
  getCreditBalanceMock.mockReset();
  getCreditPacksMock.mockReset();
  getCreditTransactionsMock.mockReset();
  getModelRatesMock.mockReset();
  getModelRatesMock.mockResolvedValue([
    { model: "sonnet", is_free: false, baseline_credits_per_chat: 12 },
  ]);
});

describe("useBillingPage", () => {
  it("残高・パック・履歴をまとめて取得する", async () => {
    getCreditBalanceMock.mockResolvedValue({ balance: 12000 });
    getCreditPacksMock.mockResolvedValue([
      { id: "starter", name: "スターター", price_jpy: 500, credits: 30000 },
    ]);
    getCreditTransactionsMock.mockResolvedValue([
      {
        id: "t1",
        amount: 30000,
        balance_after: 30000,
        transaction_type: "purchase",
        description: null,
        created_at: "2026-06-13T00:00:00Z",
      },
    ]);

    const { result } = renderHook(() => useBillingPage());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.balance).toBe(12000);
    expect(result.current.packs).toHaveLength(1);
    expect(result.current.transactions).toHaveLength(1);
    // 有料モデル（Sonnet）の標準消費レートも取得する（回数目安に使う）
    expect(result.current.paidRate).toBe(12);
    expect(result.current.error).toBeNull();
  });

  it("いずれかの取得に失敗したら error を立てる", async () => {
    getCreditBalanceMock.mockResolvedValue({ balance: 0 });
    getCreditPacksMock.mockRejectedValue(new Error("パック取得失敗"));
    getCreditTransactionsMock.mockResolvedValue([]);

    const { result } = renderHook(() => useBillingPage());

    await waitFor(() => {
      expect(result.current.error).toBe("パック取得失敗");
    });
    expect(result.current.loading).toBe(false);
  });

  it("初期状態は loading=true", () => {
    getCreditBalanceMock.mockResolvedValue({ balance: 0 });
    getCreditPacksMock.mockResolvedValue([]);
    getCreditTransactionsMock.mockResolvedValue([]);

    const { result } = renderHook(() => useBillingPage());

    expect(result.current.loading).toBe(true);
  });
});
