import { useState, useEffect, useCallback } from "react";
import {
  summarizeBlogArticles,
  getBlogSummaryCache,
  getBlogSummaryCacheStatus,
} from "../../api";
import { FALLBACK_MESSAGES } from "../../constants/messages";
import type { BlogArticle } from "../../types";
import { isInProgressStatus } from "../../utils/taskStatus";
import { useTaskPolling } from "../useTaskPolling";

/**
 * ブログ記事の AI サマリのポーリングを管理するフック。
 * useBlogAccountManager から AI 分析ロジックを分離する。
 */
export function useBlogSummaryPolling(articles: BlogArticle[]) {
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const { startPolling, isPolling } = useTaskPolling({
    checkStatus: getBlogSummaryCacheStatus,
    onCompleted: async () => {
      const cached = await getBlogSummaryCache();
      if (cached.available && cached.summary) {
        setSummary(cached.summary);
      }
      setSummaryLoading(false);
    },
    onFailed: (err) => {
      setSummaryError(err.message || FALLBACK_MESSAGES.BLOG_SUMMARY_FAILED);
      setSummaryLoading(false);
    },
  });

  // 初回マウント時: pending/processing ならポーリングを再開する
  useEffect(() => {
    getBlogSummaryCache()
      .then((cached) => {
        if (isInProgressStatus(cached.status)) {
          setSummaryLoading(true);
          startPolling();
          return;
        }
        if (cached.available && cached.summary) {
          setSummary(cached.summary);
        }
      })
      .catch(() => {});
  }, [startPolling]);

  /**
   * AI 分析を開始する。202 レスポンス後にポーリングを開始する。
   */
  const handleSummarize = useCallback(async () => {
    if (articles.length === 0) return;
    setSummaryLoading(true);
    setSummary(null);
    setSummaryError(null);
    try {
      const result = await summarizeBlogArticles();
      if (!result.available && result.status !== "pending") {
        setSummaryError(FALLBACK_MESSAGES.BLOG_SUMMARY_UNAVAILABLE);
        setSummaryLoading(false);
        return;
      }
      if (!isPolling) {
        startPolling();
      }
    } catch (e) {
      setSummaryError(e instanceof Error ? e.message : FALLBACK_MESSAGES.BLOG_SUMMARY_FAILED);
      setSummaryLoading(false);
    }
  }, [articles, isPolling, startPolling]);

  return { summary, summaryLoading, summaryError, handleSummarize };
}
