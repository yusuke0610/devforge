import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FALLBACK_MESSAGES } from "../constants/messages";
import { useAgentUsageSummary } from "./useAgentUsageSummary";

const getAgentUsageSummaryMock = vi.fn();

vi.mock("../api/billing", () => ({
  getAgentUsageSummary: (...args: unknown[]) => getAgentUsageSummaryMock(...args),
}));

beforeEach(() => {
  getAgentUsageSummaryMock.mockReset();
});

describe("useAgentUsageSummary", () => {
  it("enabled=true でモデル別サマリを取得し getUsage で引ける", async () => {
    getAgentUsageSummaryMock.mockResolvedValue([
      { model: "sonnet", chat_count: 3, input_tokens: 100, output_tokens: 200, credit_cost: 810 },
    ]);

    const { result } = renderHook(() => useAgentUsageSummary(true));

    await waitFor(() => {
      expect(result.current.getUsage("sonnet")?.chat_count).toBe(3);
    });
    // 未利用モデルは undefined
    expect(result.current.getUsage("haiku")).toBeUndefined();
  });

  it("enabled=false の間は取得しない", () => {
    getAgentUsageSummaryMock.mockResolvedValue([]);

    const { result } = renderHook(() => useAgentUsageSummary(false));

    expect(getAgentUsageSummaryMock).not.toHaveBeenCalled();
    expect(result.current.getUsage("sonnet")).toBeUndefined();
  });

  it("取得失敗時は error にメッセージが入る", async () => {
    getAgentUsageSummaryMock.mockRejectedValue("network down");

    const { result } = renderHook(() => useAgentUsageSummary(true));

    await waitFor(() => {
      expect(result.current.error).toBe(FALLBACK_MESSAGES.USAGE_SUMMARY);
    });
  });
});
