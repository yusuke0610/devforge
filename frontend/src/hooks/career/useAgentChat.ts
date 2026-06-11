/**
 * Agent チャット（ADR-0010）の状態管理フック。
 *
 * チャット履歴・送信中フラグ・エラーを保持し、送信時に編集中フォームから
 * リクエストコンテキストを組み立てて `POST /api/agent/chat` を呼ぶ。
 * operations の適用は呼び出し側（ウィジェット → CareerResumeForm の setForm）が行う。
 */

import { useCallback, useState } from "react";

import { postAgentChat } from "../../api/agent";
import type { AgentOperation, ProjectTarget } from "../../api/types";
import { FALLBACK_MESSAGES } from "../../constants/messages";
import type { CareerFormState } from "../../payloadBuilders";
import {
  buildAgentResumeContext,
  type AgentScope,
} from "../../utils/agentOperations";

/** チャット 1 件分（ユーザー発話 or AI 応答）。 */
export type AgentChatEntry = {
  role: "user" | "assistant";
  text: string;
  /** AI 応答のみ。フォームへ反映できる差分（適用済みなら null にする） */
  operations: AgentOperation[] | null;
  /** 送信時点のスコープ・対象（適用時に参照する） */
  scope: AgentScope;
  target: ProjectTarget | null;
};

export function useAgentChat() {
  const [entries, setEntries] = useState<AgentChatEntry[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = useCallback(
    async (
      form: CareerFormState,
      scope: AgentScope,
      target: ProjectTarget | null,
      prompt: string,
    ) => {
      setError(null);
      setSending(true);
      setEntries((prev) => [
        ...prev,
        { role: "user", text: prompt, operations: null, scope, target },
      ]);
      try {
        const response = await postAgentChat({
          scope,
          prompt,
          resume: buildAgentResumeContext(form),
          target: scope === "project" ? target : null,
        });
        setEntries((prev) => [
          ...prev,
          {
            role: "assistant",
            text: response.message,
            operations: response.operations?.length ? response.operations : null,
            scope,
            target,
          },
        ]);
      } catch (e) {
        setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.AGENT_CHAT);
      } finally {
        setSending(false);
      }
    },
    [],
  );

  /** 指定エントリの operations を適用済み（null）にする。 */
  const markApplied = useCallback((index: number) => {
    setEntries((prev) =>
      prev.map((entry, i) => (i === index ? { ...entry, operations: null } : entry)),
    );
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { entries, sending, error, send, markApplied, clearError };
}
