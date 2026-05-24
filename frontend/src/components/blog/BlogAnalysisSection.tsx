import { marked } from "marked";
import { AsyncTaskLoading } from "../ui/AsyncTaskLoading";
import { LOADING_MESSAGES } from "../../constants/messages";
import styles from "./BlogPage.module.css";

/** BlogAnalysisSection のプロパティ型 */
type BlogAnalysisSectionProps = {
  /** AI 分析実行中フラグ */
  summaryLoading: boolean;
  /** AI 分析結果テキスト */
  summary: string | null;
};

/**
 * BlogPage の AI 分析結果セクション。
 * summaryLoading または summary がある場合のみ表示する。
 */
export function BlogAnalysisSection({ summaryLoading, summary }: BlogAnalysisSectionProps) {
  if (!summaryLoading && !summary) return null;

  const summaryHtml = summary ? (marked.parse(summary, { async: false }) as string) : "";

  return (
    <div className={styles.aiSection}>
      <h2>AI 分析結果</h2>
      {summaryLoading ? (
        <AsyncTaskLoading label={LOADING_MESSAGES.BLOG_ANALYSIS} />
      ) : (
        <div className={styles.summaryText} dangerouslySetInnerHTML={{ __html: summaryHtml }} />
      )}
    </div>
  );
}
