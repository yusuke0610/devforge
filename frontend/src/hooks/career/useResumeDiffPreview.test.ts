import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { VALIDATION_MESSAGES } from "../../constants/messages";
import type { CareerFormState } from "../../payloadBuilders";
import { useResumeDiffPreview } from "./useResumeDiffPreview";

vi.mock("../../api/resumes", () => ({
  getCareerResumePreview: vi.fn(),
}));

import { getCareerResumePreview } from "../../api/resumes";

const mockPreview = getCareerResumePreview as unknown as ReturnType<typeof vi.fn>;

const validForm: CareerFormState = {
  full_name: "山田 太郎",
  career_summary: "サマリー",
  self_pr: "自己PR",
  experiences: [],
  qualifications: [],
};

const baseline: CareerFormState = { ...validForm, full_name: "佐藤 花子" };

beforeEach(() => {
  mockPreview.mockReset();
  mockPreview.mockResolvedValue({ html: "<p>preview</p>", css: ".c{}" });
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useResumeDiffPreview", () => {
  it("成功: baseline と編集中の HTML を取得する", async () => {
    const { result } = renderHook(() => useResumeDiffPreview(validForm, baseline, true));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(result.current.baselineHtml).toBe("<p>preview</p>");
    expect(result.current.editedHtml).toBe("<p>preview</p>");
    expect(result.current.css).toBe(".c{}");
    expect(result.current.error).toBeNull();
  });

  it("失敗: 取得が reject したらエラーメッセージを立てる", async () => {
    mockPreview.mockRejectedValue(new Error("取得失敗"));
    const { result } = renderHook(() => useResumeDiffPreview(validForm, baseline, true));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(result.current.error).toBe("取得失敗");
    expect(result.current.editedHtml).toBeNull();
  });

  it("入力不正: payload 化できない form はエラーを立て API を呼ばない", async () => {
    const invalidForm: CareerFormState = { ...validForm, full_name: "" };
    const { result } = renderHook(() => useResumeDiffPreview(invalidForm, baseline, true));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(result.current.error).toBe(VALIDATION_MESSAGES.FULL_NAME_REQUIRED);
    expect(result.current.editedHtml).toBeNull();
    // baseline 側だけ呼ばれ、編集中側（不正）は呼ばれない
    expect(mockPreview).toHaveBeenCalledTimes(1);
  });

  it("baseline=null のときは baselineHtml を null にする（古い左ペインを出さない）", async () => {
    const { result, rerender } = renderHook(
      ({ b }: { b: CareerFormState | null }) => useResumeDiffPreview(validForm, b, true),
      { initialProps: { b: baseline as CareerFormState | null } },
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(result.current.baselineHtml).toBe("<p>preview</p>");

    // baseline が無くなったら（未保存化）キャッシュ済みでも null に倒す
    rerender({ b: null });
    expect(result.current.baselineHtml).toBeNull();
  });

  it("無効化中(enabled=false)は何もしない", async () => {
    renderHook(() => useResumeDiffPreview(validForm, baseline, false));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });
    expect(mockPreview).not.toHaveBeenCalled();
  });
});
