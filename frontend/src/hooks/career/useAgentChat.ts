/**
 * Agent チャット（ADR-0010）の状態管理フック。
 *
 * チャット履歴・送信中フラグ・エラーを保持し、送信時に編集中フォームから
 * リクエストコンテキストを組み立てて `POST /api/agent/chat` を呼ぶ。
 * operations の適用は呼び出し側（ウィジェット → CareerResumeForm の setForm）が行う。
 */

import { useCallback, useState } from "react";

import { postAgentChat } from "../../api/agent";
import type { AgentHistoryEntry, AgentOperation, ProjectTarget } from "../../api/types";
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
  /** AI 応答のみ。依頼が曖昧なとき LLM が提示する「次の依頼文」候補 */
  suggestions: string[] | null;
  /** 送信時点のスコープ・対象（適用時に参照する） */
  scope: AgentScope;
  target: ProjectTarget | null;
  /**
   * マルチターン履歴として LLM に送るテキスト。user は依頼文そのまま、
   * assistant は受信時の応答 JSON 文字列（operations が適用済みで
   * null になっても履歴用の原文はここに残る）
   */
  historyText: string;
};

/** 履歴として送る最大エントリ数（3 往復。backend schema の max_length=6 と同期） */
const HISTORY_LIMIT = 6;

/**
 * entries から API に送る履歴を構築する。
 * assistant 応答とペアになった往復のみを対象にし（送信エラーで応答が無い
 * user 発話は除外）、直近 HISTORY_LIMIT 件に切り詰める。
 */
function buildHistory(entries: AgentChatEntry[]): AgentHistoryEntry[] {
  const history: AgentHistoryEntry[] = [];
  entries.forEach((entry, i) => {
    if (entry.role === "user" && entries[i + 1]?.role !== "assistant") return;
    history.push({ role: entry.role, text: entry.historyText });
  });
  return history.slice(-HISTORY_LIMIT);
}

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
        {
          role: "user",
          text: prompt,
          operations: null,
          suggestions: null,
          scope,
          target,
          historyText: prompt,
        },
      ]);
      try {
        const response = await postAgentChat({
          scope,
          prompt,
          resume: buildAgentResumeContext(form),
          target: scope === "project" ? target : null,
          history: buildHistory(entries),
        });
        setEntries((prev) => [
          ...prev,
          {
            role: "assistant",
            text: response.message,
            operations: response.operations?.length ? response.operations : null,
            suggestions: response.suggestions?.length ? response.suggestions : null,
            scope,
            target,
            // 応答 JSON の原文を履歴用に保持する（出力形式の実例としても機能する）
            historyText: JSON.stringify({
              message: response.message,
              operations: response.operations ?? [],
            }),
          },
        ]);
      } catch (e) {
        setError(e instanceof Error ? e.message : FALLBACK_MESSAGES.AGENT_CHAT);
      } finally {
        setSending(false);
      }
    },
    // buildHistory が最新の entries を参照するため依存に含める
    [entries],
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
