import { useState } from "react";

import { useBlogAccountManager } from "../../hooks/blog/useBlogAccountManager";
import { BlogScoreCard } from "./BlogScoreCard";
import { BlogPlatformList } from "./BlogPlatformList";
import { BlogArticleList } from "./BlogArticleList";
import { InlineSpinner } from "../ui/InlineSpinner";
import { useMessageToast } from "../ui/toast";
import shared from "../../styles/shared.module.css";

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

  // アカウント連携/同期/解除の成否をトーストで通知する（成功は自動消去、失敗は手動クローズ）。
  useMessageToast(success, "success");
  useMessageToast(accountError, "error");

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
