import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CareerFormState } from "../../payloadBuilders";
import { useAgentChat } from "./useAgentChat";

const postAgentChatMock = vi.fn();

vi.mock("../../api/agent", () => ({
  postAgentChat: (...args: unknown[]) => postAgentChatMock(...args),
}));

/** 最小のフォーム state（コンテキスト変換が通ればよい）。 */
const form = {
  full_name: "",
  email: "",
  github_url: "",
  career_summary: "要約",
  self_pr: "PR",
  experiences: [],
  qualifications: [],
} as unknown as CareerFormState;

beforeEach(() => {
  postAgentChatMock.mockReset();
});

describe("useAgentChat", () => {
  it("送信成功で user / assistant エントリが追加され operations を保持する", async () => {
    postAgentChatMock.mockResolvedValue({
      message: "提案です",
      operations: [{ field: "career_summary", value: "改善案" }],
    });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "career_summary", null, "改善して");
    });

    expect(result.current.entries).toHaveLength(2);
    expect(result.current.entries[0]).toMatchObject({ role: "user", text: "改善して" });
    expect(result.current.entries[1]).toMatchObject({
      role: "assistant",
      text: "提案です",
      operations: [{ field: "career_summary", value: "改善案" }],
    });
    // scope=career_summary では target を送らない
    expect(postAgentChatMock).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "career_summary", target: null }),
    );
  });

  it("API 失敗時は error にメッセージが入り sending が解除される", async () => {
    postAgentChatMock.mockRejectedValue(new Error("AI の応答取得に失敗しました。"));
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("AI の応答取得に失敗しました。");
    });
    expect(result.current.sending).toBe(false);
    // user エントリは残る（assistant は追加されない）
    expect(result.current.entries).toHaveLength(1);
  });

  it("markApplied で該当エントリの operations が null になる", async () => {
    postAgentChatMock.mockResolvedValue({
      message: "提案です",
      operations: [{ field: "self_pr", value: "改善案" }],
    });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して");
    });
    act(() => {
      result.current.markApplied(1);
    });

    expect(result.current.entries[1].operations).toBeNull();
  });

  it("operations が空配列なら null として保持する（反映ボタンを出さない契約）", async () => {
    postAgentChatMock.mockResolvedValue({ message: "提案なし", operations: [] });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して");
    });

    expect(result.current.entries[1].operations).toBeNull();
  });
});
