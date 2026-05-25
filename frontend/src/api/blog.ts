import { request } from "./client";
import { PATHS } from "./paths";
import type { BlogAccount, BlogArticle } from "../types";

export interface BlogScoreArticle {
  id: string;
  title: string;
  url: string;
  published_at: string | null;
  likes_count: number;
  tags: string[];
  is_tech: boolean;
}

export interface BlogScoreResponse {
  tech_article_count: number;
  total_article_count: number;
  avg_monthly_posts: number;
  avg_likes: number;
  articles: BlogScoreArticle[];
}

/**
 * 連携アカウント一覧を取得する。
 */
export function getBlogAccounts(): Promise<BlogAccount[]> {
  return request<BlogAccount[]>(PATHS.blog.accounts);
}

/**
 * 連携アカウントを登録する。
 */
export function addBlogAccount(
  platform: "zenn" | "note" | "qiita",
  username: string,
): Promise<BlogAccount> {
  return request<BlogAccount>(PATHS.blog.accounts, {
    method: "POST",
    body: JSON.stringify({ platform, username }),
  });
}

/**
 * 連携アカウントの username を更新する。
 */
export function updateBlogAccount(
  platform: "zenn" | "note" | "qiita",
  username: string,
): Promise<BlogAccount> {
  return request<BlogAccount>(PATHS.blog.accountByPlatform(platform), {
    method: "PATCH",
    body: JSON.stringify({ username }),
  });
}

/**
 * 連携アカウントを解除する。
 */
export async function deleteBlogAccount(id: string): Promise<void> {
  await request<void>(PATHS.blog.accountById(id), {
    method: "DELETE",
  });
}

/**
 * DB の記事一覧を取得する。
 */
export function getBlogArticles(platform?: string): Promise<BlogArticle[]> {
  return request<BlogArticle[]>(PATHS.blog.articles(platform));
}

/**
 * 外部 API から記事を同期する。
 */
export function syncBlogAccount(
  accountId: string,
): Promise<{ synced_count: number; total_count: number }> {
  return request<{ synced_count: number; total_count: number }>(
    PATHS.blog.accountSync(accountId),
    { method: "POST" },
  );
}

/**
 * ブログスコアリング結果を取得する。
 */
export function getBlogScore(): Promise<BlogScoreResponse> {
  return request<BlogScoreResponse>(PATHS.blog.score);
}
