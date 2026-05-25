import { useState } from "react";

import { useBlogAccountManager } from "../../hooks/blog/useBlogAccountManager";
import { BlogScoreCard } from "./BlogScoreCard";
import { BlogPlatformList } from "./BlogPlatformList";
import { BlogArticleList } from "./BlogArticleList";
import { InlineSpinner } from "../ui/InlineSpinner";
import shared from "../../styles/shared.module.css";
import styles from "./BlogPage.module.css";

type PlatformFilter = "all" | "zenn" | "note" | "qiita";

/**
 * ブログ連携ページ。固定プラットフォーム一覧でアカウント連携 → 記事一覧・投稿サマリ。
 */
export function BlogPage() {
  const [filter, setFilter] = useState<PlatformFilter>("all");

  const {
    accounts,
    articles,
    loading,
    accountError,
    success,
    draftUsernames,
    setDraftUsernames,
    savingPlatform,
    syncingPlatform,
    accountMap,
    handleSave,
    handleSync,
    handleDelete,
  } = useBlogAccountManager(filter);

  if (loading) {
    return (
      <>
        <div className={shared.pageHeader}>
          <h1>ブログ連携</h1>
        </div>
        <div className={shared.pageBody}>
          <InlineSpinner label="読み込み中..." />
        </div>
      </>
    );
  }

  return (
    <>
      <div className={shared.pageHeader}>
        <h1>ブログ連携</h1>
      </div>

      <div className={shared.pageBody}>
        {accountError && <p className={styles.errorMessage}>{accountError}</p>}
        {success && <p className={styles.successMessage}>{success}</p>}

        <BlogPlatformList
          accountMap={accountMap}
          draftUsernames={draftUsernames}
          setDraftUsernames={setDraftUsernames}
          savingPlatform={savingPlatform}
          syncingPlatform={syncingPlatform}
          onSave={handleSave}
          onSync={handleSync}
          onDelete={handleDelete}
        />

        {articles.length > 0 && <BlogScoreCard />}

        {accounts.length > 0 && (
          <BlogArticleList
            articles={articles}
            filter={filter}
            onFilterChange={setFilter}
          />
        )}
      </div>
    </>
  );
}
