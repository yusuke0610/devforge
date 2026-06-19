import { request } from "./client";
import { PATHS } from "./paths";
import type { AgentChatRequest, AgentChatResponse } from "./types";

/**
 * Agent チャット（ADR-0010）。選択スコープの内容とプロンプトを送り、
 * 職務経歴書への差分 operations を受け取る。DB は更新されない。
 */
export function postAgentChat(payload: AgentChatRequest): Promise<AgentChatResponse> {
  return request<AgentChatResponse>(PATHS.agent.chat, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
