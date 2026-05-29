import { request } from "./client";
import { PATHS } from "./paths";
import type { TaskStatusResponse } from "./shared";

export interface TaskProgress {
  task_id: string;
  step_index: number;
  total_steps: number;
  step_label: string | null;
  sub_progress: { done: number; total: number } | null;
}

export interface GitHubLinkPayload {
  include_forks?: boolean;
}

/** コントリビューションカレンダーの 1 日分 */
export interface ContributionDay {
  /** ISO 8601 形式の日付 (YYYY-MM-DD) */
  date: string;
  /** その日のコントリビューション数 */
  count: number;
  /** GitHub の濃淡レベル (0–4) */
  level: number;
}

/** 直近1年のコントリビューションカレンダー（GitHub の緑の四角） */
export interface ContributionCalendar {
  /** 期間内のコントリビューション総数 */
  total_contributions: number;
  /** 週ごとの日配列（列=週、各週は最大7日） */
  weeks: ContributionDay[][];
}

export interface GitHubLinkResponse {
  username: string;
  repos_analyzed: number;
  unique_skills: number;
  analyzed_at: string;
  languages: Record<string, number>;
  /** 依存関係から検出したフレームワーク名 → 使用リポジトリ数 */
  detected_frameworks: Record<string, number>;
  /** ルートファイルから検出した DevTools 名 → 使用リポジトリ数 */
  detected_devtools: Record<string, number>;
  /** ルートファイルから検出したインフラツール名 → 使用リポジトリ数 */
  detected_infras: Record<string, number>;
  /** 直近1年のコントリビューションカレンダー（取得失敗時は null） */
  contribution_calendar?: ContributionCalendar | null;
}

export interface CachedGitHubLinkResponse {
  result: GitHubLinkResponse | null;
  status?: string;
  error_message?: string;
  error_code?: string;
  /** 連携自体は完了したが部分的に欠落した場合の警告 */
  warning_message?: string;
}

/**
 * GitHub 連携を開始します（202 非同期）。
 */
export function runGitHubLink(payload: GitHubLinkPayload): Promise<{ status: string }> {
  return request<{ status: string }>(PATHS.githubLink.run, {
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
export function getGitHubLinkProgress(): Promise<TaskProgress> {
  return request<TaskProgress>(PATHS.githubLink.progress);
}

/**
 * 失敗した GitHub 連携タスクを手動で再実行します（202 非同期）。
 */
export function retryGitHubLink(
  payload: GitHubLinkPayload = {},
): Promise<{ status: string }> {
  return request<{ status: string }>(PATHS.githubLink.runRetry, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
