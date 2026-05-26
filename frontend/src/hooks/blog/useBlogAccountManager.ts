import { useState, useEffect, useCallback } from "react";

import {
  getBlogAccounts,
  addBlogAccount,
  updateBlogAccount,
  deleteBlogAccount,
  getBlogArticles,
  syncBlogAccount,
} from "../../api";
import { FALLBACK_MESSAGES } from "../../constants/messages";
import type { BlogAccount, BlogArticle } from "../../types";

export type PlatformKey = "zenn" | "note" | "qiita";

export type PlatformAction = "saving" | "syncing" | "updating" | "deleting";

/** プラットフォーム別の進行中アクション集合。値が無いキーは「アイドル」を意味する。 */
export type PlatformActionMap = Partial<Record<PlatformKey, PlatformAction>>;

/**
 * PlatformActionMap への純粋な更新関数。
 *
 * クリア（``action === null``）時に ``expectedAction`` を指定すると、
 * 現在のアクションが ``expectedAction`` と一致する場合のみ削除する。
 * これにより、同一プラットフォームで先発アクションの finally が
 * 後発アクションを clobber することを防ぐ（race condition ガード）。
 *
 * 単体テストのため、フック内のクロージャから切り出して export している。
 */
export function reduceActions(
  prev: PlatformActionMap,
  platform: PlatformKey,
  action: PlatformAction | null,
  expectedAction?: PlatformAction,
): PlatformActionMap {
  if (action == null) {
    if (expectedAction !== undefined && prev[platform] !== expectedAction) {
      return prev;
    }
    const next = { ...prev };
    delete next[platform];
    return next;
  }
  return { ...prev, [platform]: action };
}

/**
 * BlogPage のブログアカウント管理・同期ロジックを提供するカスタムフック。
 *
 * 4 種類の per-platform lifecycle（saving / syncing / updating / deleting）は
 * 単一の ``PlatformActionMap`` で集約管理する。外部には従来通り
 * ``savingPlatform`` / ``syncingPlatform`` 等の派生値で公開する。
 */
export function useBlogAccountManager(filter: "all" | "zenn" | "note" | "qiita") {
  const [accounts, setAccounts] = useState<BlogAccount[]>([]);
  const [articles, setArticles] = useState<BlogArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [accountError, setAccountError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  /** プラットフォームごとの入力中ユーザー名 */
  const [draftUsernames, setDraftUsernames] = useState<Record<string, string>>({
    zenn: "",
    note: "",
    qiita: "",
  });

  /** プラットフォーム別の進行中アクション。同時に複数プラットフォームを操作する余地を残す。 */
  const [actions, setActions] = useState<PlatformActionMap>({});

  /** 指定プラットフォームのアクションをセット/解除する（reduceActions の薄いラッパ）。 */
  const setAction = useCallback(
    (
      platform: PlatformKey,
      action: PlatformAction | null,
      expectedAction?: PlatformAction,
    ) => {
      setActions((prev) => reduceActions(prev, platform, action, expectedAction));
    },
    [],
  );

  /** 指定アクションを実行中のプラットフォームを返す（最初の 1 件、なければ null）。 */
  const findPlatformWithAction = (target: PlatformAction): PlatformKey | null => {
    for (const [platform, action] of Object.entries(actions)) {
      if (action === target) return platform as PlatformKey;
    }
    return null;
  };

  /** アカウント map（platform → account） */
  const accountMap = new Map(accounts.map((a) => [a.platform, a]));

  /**
   * アカウント一覧と記事一覧を再取得する。
   */
  const loadData = useCallback(async () => {
    try {
      const fetchedAccounts = await getBlogAccounts();
      setAccounts(fetchedAccounts);
      if (fetchedAccounts.length > 0) {
        const arts = await getBlogArticles(filter === "all" ? undefined : filter);
        setArticles(arts);
      } else {
        setArticles([]);
      }
    } catch (e) {
      setAccountError(e instanceof Error ? e.message : FALLBACK_MESSAGES.BLOG_FETCH);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /**
   * 保存/更新後の自動同期を試みる。成功時は formatSuccess の文言、
   * 失敗時は fallbackMessage を success にセットしつつ同期エラーを accountError に出す。
   */
  const attemptAutoSync = async (
    accountId: string,
    formatSuccess: (synced: number, total: number) => string,
    fallbackMessage: string,
  ) => {
    try {
      const result = await syncBlogAccount(accountId);
      await loadData();
      setSuccess(formatSuccess(result.synced_count, result.total_count));
    } catch (syncErr) {
      setSuccess(fallbackMessage);
      setAccountError(
        syncErr instanceof Error ? syncErr.message : FALLBACK_MESSAGES.BLOG_SYNC,
      );
    }
  };

  /**
   * ユーザー名を保存（連携）し、自動で記事を同期する。
   */
  const handleSave = async (platform: PlatformKey) => {
    const username = draftUsernames[platform]?.trim();
    if (!username) return;
    setAction(platform, "saving");
    setAccountError(null);
    setSuccess(null);
    try {
      const account = await addBlogAccount(platform, username);
      setDraftUsernames((prev) => ({ ...prev, [platform]: "" }));
      await loadData();
      await attemptAutoSync(
        account.id,
        (synced, total) => `${synced}件の記事を取得しました（合計: ${total}件）`,
        "アカウントを連携しました",
      );
    } catch (e) {
      setAccountError(e instanceof Error ? e.message : FALLBACK_MESSAGES.BLOG_LINK);
    } finally {
      setAction(platform, null, "saving");
    }
  };

  /**
   * 記事を同期する。
   */
  const handleSync = async (platform: PlatformKey) => {
    const account = accountMap.get(platform);
    if (!account) return;
    setAction(platform, "syncing");
    setAccountError(null);
    setSuccess(null);
    try {
      const result = await syncBlogAccount(account.id);
      await loadData();
      setSuccess(
        `${result.synced_count}件の新しい記事を取得しました（合計: ${result.total_count}件）`,
      );
    } catch (e) {
      setAccountError(e instanceof Error ? e.message : FALLBACK_MESSAGES.BLOG_SYNC_SIMPLE);
    } finally {
      setAction(platform, null, "syncing");
    }
  };

  /**
   * アカウントを解除する。
   */
  const handleDelete = async (platform: PlatformKey) => {
    const account = accountMap.get(platform);
    if (!account) return;
    setAction(platform, "deleting");
    setAccountError(null);
    setSuccess(null);
    try {
      await deleteBlogAccount(account.id);
      await loadData();
      setSuccess("アカウントを解除しました");
    } catch (e) {
      setAccountError(e instanceof Error ? e.message : FALLBACK_MESSAGES.BLOG_UNLINK);
    } finally {
      setAction(platform, null, "deleting");
    }
  };

  /**
   * 連携済みアカウントの username を更新し、自動で記事を再同期する。
   */
  const handleUpdate = async (platform: PlatformKey, username: string) => {
    const account = accountMap.get(platform);
    if (!account) return false;
    const trimmedUsername = username.trim();
    if (!trimmedUsername) return false;
    setAction(platform, "updating");
    setAccountError(null);
    setSuccess(null);
    try {
      await updateBlogAccount(platform, trimmedUsername);
      setDraftUsernames((prev) => ({ ...prev, [platform]: "" }));
      await loadData();
      await attemptAutoSync(
        account.id,
        (synced, total) =>
          `usernameを更新し、${synced}件の記事を取得しました（合計: ${total}件）`,
        "usernameを更新しました。再同期してください。",
      );
      return true;
    } catch (e) {
      setAccountError(e instanceof Error ? e.message : FALLBACK_MESSAGES.BLOG_USERNAME_UPDATE);
      return false;
    } finally {
      setAction(platform, null, "updating");
    }
  };

  return {
    accounts,
    articles,
    loading,
    accountError,
    success,
    draftUsernames,
    setDraftUsernames,
    savingPlatform: findPlatformWithAction("saving"),
    syncingPlatform: findPlatformWithAction("syncing"),
    updatingPlatform: findPlatformWithAction("updating"),
    deletingPlatform: findPlatformWithAction("deleting"),
    accountMap,
    handleSave,
    handleSync,
    handleDelete,
    handleUpdate,
  };
}
