import { FALLBACK_MESSAGES } from "../constants/messages";
import { request } from "./client";
import { getBlobUrl } from "./download";
import { PATHS } from "./paths";
import type {
  AgentChatRequest,
  AgentChatResponse,
  TaskAcceptedResponse,
  TaskStatusResponse,
} from "./types";

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
 * GitHub 連携データからの経歴書ドラフト生成をバックグラウンドで開始する（202 非同期 / ADR-0018）。
 * 生成物は resume_draft_cache に保存され、完了後に {@link fetchResumeDraftPdfBlobUrl} で取得する。
 * 失敗時は ApiError（409 = 連携データ不足）を送出する。
 * モデルは Claude Haiku 固定（ADR-0023 でマルチプロバイダ・モデル選択を撤去）。
 */
export function startResumeDraft(): Promise<TaskAcceptedResponse> {
  return request<TaskAcceptedResponse>(PATHS.agent.resumeDraftRun, {
    method: "POST",
    body: JSON.stringify({ model: "haiku" }),
  });
}

/**
 * 経歴書ドラフト生成タスクのステータスを取得する（ポーリング用 / ADR-0018）。
 */
export function getResumeDraftStatus(): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>(PATHS.agent.resumeDraftStatus);
}

/**
 * 完了済みの経歴書ドラフトを取得し、プレビュー用の Blob URL を返す（ADR-0018）。
 * 未完了・結果なしの場合は ApiError（409）を送出する。
 */
export function fetchResumeDraftPdfBlobUrl(): Promise<string> {
  return getBlobUrl(
    PATHS.agent.resumeDraftPdf,
    { method: "GET" },
    FALLBACK_MESSAGES.RESUME_DRAFT,
  );
}
