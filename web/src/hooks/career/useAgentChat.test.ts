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

  it("曖昧入力応答の suggestions（依頼文候補）をエントリに保持する", async () => {
    postAgentChatMock.mockResolvedValue({
      message: "どの方向で改善しますか？",
      operations: [],
      suggestions: ["300字に要約して", "成果を強調して書き直して"],
    });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "いい感じにして");
    });

    expect(result.current.entries[1].suggestions).toEqual([
      "300字に要約して",
      "成果を強調して書き直して",
    ]);
  });

  it("suggestions が無い応答では suggestions は null", async () => {
    postAgentChatMock.mockResolvedValue({ message: "提案です", operations: [] });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して");
    });

    expect(result.current.entries[1].suggestions).toBeNull();
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

  it("初回送信では history は空配列", async () => {
    postAgentChatMock.mockResolvedValue({ message: "提案です", operations: [] });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して");
    });

    expect(postAgentChatMock).toHaveBeenCalledWith(expect.objectContaining({ history: [] }));
  });

  it("2 回目の送信で直前の往復が history として送られる", async () => {
    postAgentChatMock.mockResolvedValue({
      message: "提案です",
      operations: [{ field: "self_pr", value: "改善案" }],
    });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して");
    });
    await act(async () => {
      await result.current.send(form, "self_pr", null, "もっと短くして");
    });

    expect(postAgentChatMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        prompt: "もっと短くして",
        history: [
          { role: "user", text: "改善して" },
          {
            role: "assistant",
            text: JSON.stringify({
              message: "提案です",
              operations: [{ field: "self_pr", value: "改善案" }],
              suggestions: [],
            }),
          },
        ],
      }),
    );
  });

  it("suggestions を含む応答は history の assistant text にも suggestions を載せる", async () => {
    // 1 往復目: 曖昧依頼に対し選択肢を返す（operations は空）
    postAgentChatMock.mockResolvedValueOnce({
      message: "どの方向で改善しますか？",
      operations: [],
      suggestions: ["300字に要約して", "成果を強調して書き直して"],
    });
    // 2 往復目（選択肢を選んで再送）
    postAgentChatMock.mockResolvedValue({ message: "提案です", operations: [] });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して");
    });
    await act(async () => {
      await result.current.send(form, "self_pr", null, "300字に要約して");
    });

    // 選択肢を選んだ次の送信時、history の assistant エントリに suggestions が含まれ、
    // LLM が「前ターンで選択肢を提示した」文脈を受け取れる（選択肢ループ回帰防止）
    expect(postAgentChatMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        prompt: "300字に要約して",
        history: [
          { role: "user", text: "改善して" },
          {
            role: "assistant",
            text: JSON.stringify({
              message: "どの方向で改善しますか？",
              operations: [],
              suggestions: ["300字に要約して", "成果を強調して書き直して"],
            }),
          },
        ],
      }),
    );
  });

  it("送信エラーで応答が無い user 発話は history に含めない", async () => {
    postAgentChatMock.mockRejectedValueOnce(new Error("失敗"));
    postAgentChatMock.mockResolvedValue({ message: "提案です", operations: [] });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "失敗する依頼");
    });
    await act(async () => {
      await result.current.send(form, "self_pr", null, "再送する依頼");
    });

    expect(postAgentChatMock).toHaveBeenLastCalledWith(
      expect.objectContaining({ history: [] }),
    );
  });

  it("history は直近 6 エントリ（3 往復）に切り詰められる", async () => {
    postAgentChatMock.mockResolvedValue({ message: "提案です", operations: [] });
    const { result } = renderHook(() => useAgentChat());

    // 5 回目の送信時点で過去 4 往復（8 エントリ）が 6 件に切り詰められる
    for (let i = 1; i <= 5; i++) {
      await act(async () => {
        await result.current.send(form, "self_pr", null, `依頼${i}`);
      });
    }

    const calls = postAgentChatMock.mock.calls;
    const lastCall = calls[calls.length - 1][0] as {
      history: { role: string; text: string }[];
    };
    expect(lastCall.history).toHaveLength(6);
    // 最古の往復（依頼1）が落ち、依頼2 から始まる
    expect(lastCall.history[0]).toEqual({ role: "user", text: "依頼2" });
  });

  it("model 未指定の送信では haiku（無料）を送る", async () => {
    postAgentChatMock.mockResolvedValue({ message: "提案です", operations: [] });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して");
    });

    expect(postAgentChatMock).toHaveBeenCalledWith(expect.objectContaining({ model: "haiku" }));
  });

  it("sonnet 指定の送信では model=sonnet を送る（有料モデル / ADR-0012）", async () => {
    postAgentChatMock.mockResolvedValue({ message: "提案です", operations: [] });
    const { result } = renderHook(() => useAgentChat());

    await act(async () => {
      await result.current.send(form, "self_pr", null, "改善して", "sonnet");
    });

    expect(postAgentChatMock).toHaveBeenCalledWith(expect.objectContaining({ model: "sonnet" }));
  });

  it("experience スコープでは target を送る", async () => {
    postAgentChatMock.mockResolvedValue({ message: "提案です", operations: [] });
    const { result } = renderHook(() => useAgentChat());
    const expTarget = { experience_index: 0 };

    await act(async () => {
      await result.current.send(form, "experience", expTarget, "事業内容を改善して");
    });

    expect(postAgentChatMock).toHaveBeenCalledWith(
      expect.objectContaining({ scope: "experience", target: expTarget }),
    );
  });
});
