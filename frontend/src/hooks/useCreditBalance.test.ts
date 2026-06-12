import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FALLBACK_MESSAGES } from "../constants/messages";
import { useCreditBalance } from "./useCreditBalance";

const getCreditBalanceMock = vi.fn();

vi.mock("../api/billing", () => ({
  getCreditBalance: (...args: unknown[]) => getCreditBalanceMock(...args),
}));

beforeEach(() => {
  getCreditBalanceMock.mockReset();
});

describe("useCreditBalance", () => {
  it("enabled=true で残高を取得し balance に保持する", async () => {
    getCreditBalanceMock.mockResolvedValue({ balance: 12_000 });

    const { result } = renderHook(() => useCreditBalance(true));

    await waitFor(() => {
      expect(result.current.balance).toBe(12_000);
    });
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("enabled=false の間は取得しない（無料モデル選択中は残高 API を呼ばない）", () => {
    getCreditBalanceMock.mockResolvedValue({ balance: 100 });

    const { result } = renderHook(() => useCreditBalance(false));

    expect(getCreditBalanceMock).not.toHaveBeenCalled();
    expect(result.current.balance).toBeNull();
  });

  it("取得失敗時は error にメッセージが入り loading が解除される", async () => {
    getCreditBalanceMock.mockRejectedValue(new Error("クレジット残高が不足しています"));

    const { result } = renderHook(() => useCreditBalance(true));

    await waitFor(() => {
      expect(result.current.error).toBe("クレジット残高が不足しています");
    });
    expect(result.current.loading).toBe(false);
    expect(result.current.balance).toBeNull();
  });

  it("Error 以外の reject では fallback メッセージを使う", async () => {
    getCreditBalanceMock.mockRejectedValue("unexpected");

    const { result } = renderHook(() => useCreditBalance(true));

    await waitFor(() => {
      expect(result.current.error).toBe(FALLBACK_MESSAGES.CREDIT_BALANCE);
    });
  });

  it("refresh で最新残高に更新される", async () => {
    getCreditBalanceMock.mockResolvedValueOnce({ balance: 1_000 });
    getCreditBalanceMock.mockResolvedValueOnce({ balance: 730 });

    const { result } = renderHook(() => useCreditBalance(true));
    await waitFor(() => {
      expect(result.current.balance).toBe(1_000);
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.balance).toBe(730);
  });
});
