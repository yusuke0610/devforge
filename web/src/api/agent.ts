import { request } from "./client";
import { getBlobUrl } from "./download";
import { PATHS } from "./paths";
import type { AgentChatRequest, AgentChatResponse, AgentModelAlias } from "./types";

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

/**
 * GitHub 連携データから経歴書ドラフト PDF を生成し、プレビュー用の Blob URL を返す（ADR-0018）。
 * ドラフトは DB に保存されない（生成物はこの PDF のみ）。
 * 失敗時は ApiError（409 = 連携データ不足 / 402 = 残高不足 / 502 = 生成失敗）を送出する。
 */
export function generateResumeDraftPdfBlobUrl(model: AgentModelAlias): Promise<string> {
  return getBlobUrl(PATHS.agent.resumeDraftPdf, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
}
