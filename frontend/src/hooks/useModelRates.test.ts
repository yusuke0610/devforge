import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useModelRates } from "./useModelRates";

const getModelRatesMock = vi.fn();

vi.mock("../api/billing", () => ({
  getModelRates: () => getModelRatesMock(),
}));

beforeEach(() => {
  getModelRatesMock.mockReset();
});

describe("useModelRates", () => {
  it("enabled=true で有料モデルの標準レートを引ける", async () => {
    getModelRatesMock.mockResolvedValue([
      { model: "haiku", is_free: true, baseline_credits_per_chat: 0 },
      { model: "sonnet", is_free: false, baseline_credits_per_chat: 12 },
    ]);

    const { result } = renderHook(() => useModelRates(true));

    await waitFor(() => {
      expect(result.current.getBaselineRate("sonnet")).toBe(12);
    });
    // 無料モデルはレートを返さない（回数目安を出さない）
    expect(result.current.getBaselineRate("haiku")).toBeNull();
  });

  it("enabled=false の間は取得しない", () => {
    getModelRatesMock.mockResolvedValue([]);

    const { result } = renderHook(() => useModelRates(false));

    expect(getModelRatesMock).not.toHaveBeenCalled();
    expect(result.current.getBaselineRate("sonnet")).toBeNull();
  });

  it("取得失敗時は error を立てる", async () => {
    getModelRatesMock.mockRejectedValue(new Error("レート取得失敗"));

    const { result } = renderHook(() => useModelRates(true));

    await waitFor(() => {
      expect(result.current.error).toBe("レート取得失敗");
    });
  });
});
