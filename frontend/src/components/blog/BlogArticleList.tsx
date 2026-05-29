import { useState } from "react";

import type { BlogArticleResponse } from "../../api/types";
import { ZennIcon } from "../icons/ZennIcon";
import { NoteIcon } from "../icons/NoteIcon";
import { QiitaIcon } from "../icons/QiitaIcon";
import styles from "./BlogPage.module.css";

type PlatformFilter = "all" | "zenn" | "note" | "qiita";

const ARTICLES_PER_PAGE = 5;

type BlogArticleListProps = {
  articles: BlogArticleResponse[];
  filter: PlatformFilter;
  onFilterChange: (filter: PlatformFilter) => void;
};

/** 記事一覧・フィルタータブ・ページネーションを描画するコンポーネント。 */
export function BlogArticleList({ articles, filter, onFilterChange }: BlogArticleListProps) {
  const [pageByFilter, setPageByFilter] = useState<Record<PlatformFilter, number>>({
    all: 1,
    zenn: 1,
    note: 1,
    qiita: 1,
  });

  const totalPages = Math.max(1, Math.ceil(articles.length / ARTICLES_PER_PAGE));
  const currentPage = Math.min(pageByFilter[filter], totalPages);
  const showPagination = articles.length > ARTICLES_PER_PAGE;
  const pageStartIndex = (currentPage - 1) * ARTICLES_PER_PAGE;
  const visibleArticles = articles.slice(pageStartIndex, pageStartIndex + ARTICLES_PER_PAGE);

  const handleFilterChange = (f: PlatformFilter) => {
    if (filter === f) return;
    onFilterChange(f);
    setPageByFilter((prev) => ({ ...prev, [f]: 1 }));
  };

  return (
    <div className={styles.articleSection}>
      <div className={styles.articleHeader}>
        <h2>記事一覧</h2>
        <div className={styles.filterTabs}>
          {(["all", "zenn", "note", "qiita"] as PlatformFilter[]).map((f) => (
            <button
              key={f}
              type="button"
              className={`${styles.filterTab} ${filter === f ? styles.filterTabActive : ""}`}
              aria-pressed={filter === f}
              onClick={() => handleFilterChange(f)}
            >
              {f === "all" ? "All" : f === "zenn" ? "Zenn" : f === "note" ? "note" : "Qiita"}
            </button>
          ))}
        </div>
      </div>

      {articles.length === 0 ? (
        <p className={styles.emptyMessage}>
          記事がありません。「同期」ボタンで記事を取得してください。
        </p>
      ) : (
        <>
          <div className={styles.articleList}>
            {visibleArticles.map((art) => (
              <a
                key={art.id}
                href={art.url}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.articleItem}
              >
                <div className={styles.articleTop}>
                  <span className={styles.articleIcon}>
                    {art.platform === "zenn" ? (
                      <ZennIcon size={16} />
                    ) : art.platform === "qiita" ? (
                      <QiitaIcon size={16} />
                    ) : (
                      <NoteIcon size={16} />
                    )}
                  </span>
                  <span className={styles.articleTitle}>{art.title}</span>
                  <span className={styles.articleDate}>{art.published_at}</span>
                </div>
                <div className={styles.articleMeta}>
                  {art.likes_count > 0 && <span>いいね: {art.likes_count}</span>}
                  {art.tags && art.tags.length > 0 && <span>タグ: {art.tags.join(", ")}</span>}
                  {art.summary && (
                    <span>
                      {art.summary.length > 80
                        ? `${art.summary.slice(0, 80)}...`
                        : art.summary}
                    </span>
                  )}
                </div>
              </a>
            ))}
          </div>

          {showPagination && (
            <div className={styles.pagination}>
              <button
                type="button"
                className={styles.paginationButton}
                onClick={() =>
                  setPageByFilter((prev) => ({ ...prev, [filter]: Math.max(1, currentPage - 1) }))
                }
                disabled={currentPage === 1}
              >
                前へ
              </button>
              <span className={styles.pageIndicator}>
                {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                className={styles.paginationButton}
                onClick={() =>
                  setPageByFilter((prev) => ({
                    ...prev,
                    [filter]: Math.min(totalPages, currentPage + 1),
                  }))
                }
                disabled={currentPage === totalPages}
              >
                次へ
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
