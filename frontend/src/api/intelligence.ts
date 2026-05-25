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

export interface AnalyzeGitHubPayload {
  include_forks?: boolean;
}

export interface AnalysisResponse {
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
}

export interface CachedAnalysisResponse {
  analysis_result: AnalysisResponse | null;
  status?: string;
  error_message?: string;
  error_code?: string;
  /** 分析自体は完了したが部分的に欠落した場合の警告 */
  warning_message?: string;
}

/**
 * GitHub プロフィールの分析を開始します（202 非同期）。
 */
export function analyzeGitHub(payload: AnalyzeGitHubPayload): Promise<{ status: string }> {
  return request<{ status: string }>(PATHS.intelligence.analyze, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * DB に保存された分析キャッシュを取得します。
 */
export function getAnalysisCache(): Promise<CachedAnalysisResponse> {
  return request<CachedAnalysisResponse>(PATHS.intelligence.cache);
}

/**
 * 分析ステータスを取得します（ポーリング用）。
 */
export function getAnalysisCacheStatus(): Promise<TaskStatusResponse> {
  return request<TaskStatusResponse>(PATHS.intelligence.cacheStatus);
}

/**
 * GitHub 分析タスクの進捗を取得します。
 * Redis が利用できない場合は step_index=0 のデフォルト値が返ります。
 */
export function getAnalysisProgress(): Promise<TaskProgress> {
  return request<TaskProgress>(PATHS.intelligence.progress);
}

/**
 * 失敗した GitHub 分析タスクを手動で再実行します（202 非同期）。
 */
export function retryAnalyzeGitHub(
  payload: AnalyzeGitHubPayload = {},
): Promise<{ status: string }> {
  return request<{ status: string }>(PATHS.intelligence.analyzeRetry, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
