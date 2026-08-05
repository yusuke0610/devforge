import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import type { ResumeDraftCandidateResponse } from "../api/types";
import { ApiError } from "../utils/appError";
import { useResumeDraftCandidates } from "./useResumeDraftCandidates";

vi.mock("../api/agent", () => ({
  getResumeDraftCandidates: vi.fn(),
}));

import { getResumeDraftCandidates } from "../api/agent";

const mockGet = vi.mocked(getResumeDraftCandidates);

function candidate(
  full_name: string,
  overrides: Partial<ResumeDraftCandidateResponse> = {},
): ResumeDraftCandidateResponse {
  return {
    full_name,
    description: "",
    duration_days: 400,
    implementation_volume: 10000,
    has_infra: false,
    technology_stacks: [],
    default_selected: true,
    reasons: [],
    ...overrides,
  };
}

describe("useResumeDraftCandidates", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("取得成功でデフォルト選択が初期値になる", async () => {
    mockGet.mockResolvedValueOnce({
      candidates: [
        candidate("o/real"),
        candidate("o/tutorial", { default_selected: false, reasons: ["learning_topic"] }),
      ],
      selection_limit: 5,
    });

    const { result } = renderHook(() => useResumeDraftCandidates());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.candidates).toHaveLength(2);
    expect(result.current.selected).toEqual(["o/real"]);
    expect(result.current.selectionLimit).toBe(5);
    expect(result.current.error).toBeNull();
  });

  it("デフォルト非選択の候補もユーザーが選び直せる", async () => {
    mockGet.mockResolvedValueOnce({
      candidates: [
        candidate("o/real"),
        candidate("o/tutorial", { default_selected: false, reasons: ["learning_topic"] }),
      ],
      selection_limit: 5,
    });

    const { result } = renderHook(() => useResumeDraftCandidates());
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => result.current.toggle("o/tutorial"));
    expect(result.current.selected).toEqual(["o/real", "o/tutorial"]);

    act(() => result.current.toggle("o/real"));
    expect(result.current.selected).toEqual(["o/tutorial"]);
  });

  it("上限に達すると追加選択しない", async () => {
    mockGet.mockResolvedValueOnce({
      candidates: [candidate("o/a"), candidate("o/b"), candidate("o/c", { default_selected: false })],
      selection_limit: 2,
    });

    const { result } = renderHook(() => useResumeDraftCandidates());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.selected).toEqual(["o/a", "o/b"]);
    act(() => result.current.toggle("o/c"));
    expect(result.current.selected).toEqual(["o/a", "o/b"]);
  });

  it("取得失敗（409 = 未連携）は error に載せ、候補は空のままにする", async () => {
    mockGet.mockRejectedValueOnce(new ApiError({ code: "VALIDATION_ERROR", message: "連携データがありません" }));

    const { result } = renderHook(() => useResumeDraftCandidates());

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.candidates).toEqual([]);
    expect(result.current.selected).toEqual([]);
    expect(result.current.error?.message).toBe("連携データがありません");
  });

  it("enabled=false の間は取得しない（連携結果が無い画面で 409 を出さない）", async () => {
    const { result } = renderHook(() => useResumeDraftCandidates(false));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(mockGet).not.toHaveBeenCalled();
    expect(result.current.candidates).toEqual([]);
    expect(result.current.error).toBeNull();
  });
});
