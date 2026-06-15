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

  it("古い refresh 応答は新しい応答を上書きしない（リクエスト順序の整合）", async () => {
    // enabled=false で自動取得を抑止し、手動 refresh の順序だけを検証する
    let resolveStale: (v: { balance: number }) => void = () => {};
    const stalePending = new Promise<{ balance: number }>((resolve) => {
      resolveStale = resolve;
    });
    // 1 回目（古い）は保留、2 回目（新しい）は即解決
    getCreditBalanceMock.mockReturnValueOnce(stalePending);
    getCreditBalanceMock.mockResolvedValueOnce({ balance: 730 });

    const { result } = renderHook(() => useCreditBalance(false));

    await act(async () => {
      void result.current.refresh(); // seq=1（保留中）
      await result.current.refresh(); // seq=2（先に解決 → 730）
    });
    expect(result.current.balance).toBe(730);

    // 後から古い応答が解決しても最新（730）を上書きしない
    await act(async () => {
      resolveStale({ balance: 9_999 });
      await stalePending;
    });
    expect(result.current.balance).toBe(730);
  });
});
