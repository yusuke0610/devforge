import { request } from "./client";
import { PATHS } from "./paths";
import type {
  CachedGitHubLinkResponse,
  GitHubSkillsResponse,
  ProgressResponse,
  SkillDisplayConfirmRequest,
  SkillDisplayProposeRequest,
  SkillDisplayProposeResponse,
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

/**
 * 連携で推論した 3 層スキル（表示名の確定込み）を取得します（ADR-0016 D11）。
 */
export function getGitHubSkills(): Promise<GitHubSkillsResponse> {
  return request<GitHubSkillsResponse>(PATHS.githubLink.skills);
}

/**
 * スキル表示名・畳み込みグループの提案を agent に依頼します（D11）。
 * agent は提案するだけで確定はしません（ユーザーがレビュー・確定する）。
 */
export function proposeSkillDisplayNames(
  payload: SkillDisplayProposeRequest,
): Promise<SkillDisplayProposeResponse> {
  return request<SkillDisplayProposeResponse>(PATHS.githubLink.skillsDisplayPropose, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * レビュー済みの表示名・畳み込みを確定・永続化します（D11）。
 * 確定後の最新スキル一覧を返します。
 */
export function confirmSkillDisplayDecisions(
  payload: SkillDisplayConfirmRequest,
): Promise<GitHubSkillsResponse> {
  return request<GitHubSkillsResponse>(PATHS.githubLink.skillsDisplayConfirm, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
