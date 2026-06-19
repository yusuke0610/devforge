import { request } from "./client";
import { PATHS } from "./paths";
import type {
  CachedGitHubLinkResponse,
  ProgressResponse,
  TaskAcceptedResponse,
  TaskStatusResponse,
} from "./types";

/**
 * GitHub 連携の開始リクエスト body。
 * backend `schemas/github_link.py:GitHubLinkRequest` 相当だが、呼び出し側で
 * 省略可能にするため include_forks を optional にした手書きの request 型（ADR-0007 論点A）。
 */
export interface GitHubLinkPayload {
  include_forks?: boolean;
}

/**
 * GitHub 連携を開始します（202 非同期）。
 */
export function runGitHubLink(payload: GitHubLinkPayload): Promise<TaskAcceptedResponse> {
  return request<TaskAcceptedResponse>(PATHS.githubLink.run, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * DB に保存された連携キャッシュを取得します。
 */
export function getGitHubLinkCache(): Promise<CachedGitHubLinkResponse> {
  return request<CachedGitHubLinkResponse>(PATHS.githubLink.cache);
}

/**
 * 連携ステータスを取得します（ポーリング用）。
 */
export function getGitHubLinkCacheStatus(): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>(PATHS.githubLink.cacheStatus);
}

/**
 * GitHub 連携タスクの進捗を取得します。
 * Redis が利用できない場合は step_index=0 のデフォルト値が返ります。
 */
export function getGitHubLinkProgress(): Promise<ProgressResponse> {
  return request<ProgressResponse>(PATHS.githubLink.progress);
}

/**
 * 失敗した GitHub 連携タスクを手動で再実行します（202 非同期）。
 */
export function retryGitHubLink(
  payload: GitHubLinkPayload = {},
): Promise<TaskAcceptedResponse> {
  return request<TaskAcceptedResponse>(PATHS.githubLink.runRetry, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
