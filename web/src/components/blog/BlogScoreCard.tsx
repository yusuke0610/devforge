import { useState, useEffect } from "react";
import { getBlogScore, type BlogScoreResponse } from "../../api/blog";
import { InlineSpinner } from "../ui/InlineSpinner";
import styles from "./BlogScoreCard.module.css";

interface StatItemProps {
  label: string;
  value: string;
}

function StatItem({ label, value }: StatItemProps) {
  return (
    <div className={styles.statItem}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}

/**
 * ブログ統計サマリを表示するカードコンポーネント。
 */
export function BlogScoreCard() {
  const [score, setScore] = useState<BlogScoreResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getBlogScore()
      .then((data) => {
        if (!cancelled) setScore(data);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className={styles.card}>
        <InlineSpinner label="集計中..." size="sm" />
      </div>
    );
  }

  if (!score) return null;

  return (
    <div className={styles.card}>
      <h3 className={styles.title}>投稿サマリ</h3>
      <div className={styles.statGrid}>
        <StatItem
          label="月間投稿頻度"
          value={`${score.avg_monthly_posts} 件/月`}
        />
        <StatItem
          label="平均いいね数"
          value={`${score.avg_likes} いいね`}
        />
        <StatItem
          label="投稿数（合計）"
          value={`${score.total_article_count} 件`}
        />
      </div>
    </div>
  );
}
