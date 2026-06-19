import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CreditBalanceProvider } from "./CreditBalanceProvider";
import { useCreditBalanceContext } from "./creditBalanceContext";

const getCreditBalanceMock = vi.fn();

vi.mock("../../api/billing", () => ({
  getCreditBalance: (...args: unknown[]) => getCreditBalanceMock(...args),
}));

function BalanceConsumer() {
  const { balance } = useCreditBalanceContext();
  return <span>balance={balance === null ? "null" : balance}</span>;
}

beforeEach(() => {
  getCreditBalanceMock.mockReset();
});

describe("CreditBalanceProvider / useCreditBalanceContext", () => {
  it("enabled=true で取得した残高を配下へ配布する", async () => {
    getCreditBalanceMock.mockResolvedValue({ balance: 8500 });

    render(
      <CreditBalanceProvider enabled>
        <BalanceConsumer />
      </CreditBalanceProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("balance=8500")).toBeTruthy();
    });
  });

  it("enabled=false（未認証）では取得せず balance は null のまま", () => {
    getCreditBalanceMock.mockResolvedValue({ balance: 8500 });

    render(
      <CreditBalanceProvider enabled={false}>
        <BalanceConsumer />
      </CreditBalanceProvider>,
    );

    expect(getCreditBalanceMock).not.toHaveBeenCalled();
    expect(screen.getByText("balance=null")).toBeTruthy();
  });

  it("Provider 外で useCreditBalanceContext を使うと例外（配線ミスを握りつぶさない）", () => {
    // render 中の throw をコンソールへ吐かせないため一時的に握る
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<BalanceConsumer />)).toThrow(
      "useCreditBalanceContext must be used within a CreditBalanceProvider",
    );
    spy.mockRestore();
  });
});
