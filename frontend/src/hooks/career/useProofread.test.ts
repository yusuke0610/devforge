import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CareerFormState } from "../../payloadBuilders";
import type { ProofreadIssue } from "../../proofread/types";
import { useProofread } from "./useProofread";

vi.mock("../../proofread/proofreadClient", () => ({
  proofreadCareerForm: vi.fn(),
}));

import { proofreadCareerForm } from "../../proofread/proofreadClient";

const mockProofread = proofreadCareerForm as unknown as ReturnType<typeof vi.fn>;

const form: CareerFormState = {
  full_name: "山田 太郎",
  career_summary: "サマリー",
  self_pr: "自己PR",
  experiences: [],
  qualifications: [],
};

const issue: ProofreadIssue = {
  fieldId: "self_pr",
  fieldLabel: "自己PR",
  ruleId: "prh",
  message: "javascript => JavaScript",
  severity: "warning",
  line: 1,
  column: 1,
  index: 0,
  excerpt: "javascript",
};

beforeEach(() => {
  mockProofread.mockReset();
  mockProofread.mockResolvedValue([issue]);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useProofread", () => {
  it("成功: enabled の間フォームを校正し指摘を返す", async () => {
    const { result } = renderHook(() => useProofread(form, true));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(mockProofread).toHaveBeenCalledTimes(1);
    expect(result.current.issues).toEqual([issue]);
    expect(result.current.proofreading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("失敗: reject したらエラーを立て指摘を空にする", async () => {
    mockProofread.mockRejectedValue(new Error("校正失敗"));
    const { result } = renderHook(() => useProofread(form, true));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(result.current.error).toBe("校正失敗");
    expect(result.current.issues).toEqual([]);
    expect(result.current.proofreading).toBe(false);
  });

  it("無効化中(enabled=false)は校正せず、結果は空のまま", async () => {
    const { result } = renderHook(() => useProofread(form, false));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(mockProofread).not.toHaveBeenCalled();
    expect(result.current.issues).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  it("enabled が false に変わると前回の指摘をクリアする", async () => {
    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) => useProofread(form, enabled),
      { initialProps: { enabled: true } },
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(result.current.issues).toEqual([issue]);

    rerender({ enabled: false });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(result.current.issues).toEqual([]);
  });
});
