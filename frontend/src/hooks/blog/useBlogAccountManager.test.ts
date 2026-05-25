import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { reduceActions, useBlogAccountManager } from "./useBlogAccountManager";
import type { BlogAccount, BlogArticle } from "../../types";

/** テスト用のダミーアカウントデータ */
const dummyAccounts: BlogAccount[] = [
  {
    id: "acc-1",
    platform: "zenn",
    username: "testuser",
    last_synced_at: "2024-01-02T00:00:00",
    created_at: "2024-01-01T00:00:00",
  },
];

/** テスト用のダミー記事データ */
const dummyArticles: BlogArticle[] = [
  {
    id: "art-1",
    platform: "zenn",
    title: "テスト記事",
    url: "https://zenn.dev/testuser/articles/test",
    published_at: "2024-01-01",
    likes_count: 10,
    summary: null,
    tags: ["TypeScript"],
  },
];

/** ../api モジュール全体をモック */
vi.mock("../../api", () => ({
  getBlogAccounts: vi.fn(),
  getBlogArticles: vi.fn(),
  addBlogAccount: vi.fn(),
  updateBlogAccount: vi.fn(),
  deleteBlogAccount: vi.fn(),
  syncBlogAccount: vi.fn(),
}));

// ── reduceActions の単体テスト ────────────────────────────────
//
// setAction の expectedAction ガード（先発アクションの finally が後発アクションを
// clobber しないこと）を locked-down するために、reduceActions を直接検証する。
// hook の useState から純粋関数として切り出してある。
describe("reduceActions", () => {
  it("action を指定すると platform にアクションをセットする", () => {
    const next = reduceActions({}, "zenn", "saving");
    expect(next).toEqual({ zenn: "saving" });
  });

  it("既存のアクションは新しいアクションで上書きされる", () => {
    const next = reduceActions({ zenn: "saving" }, "zenn", "syncing");
    expect(next).toEqual({ zenn: "syncing" });
  });

  it("action=null + expectedAction なしでは無条件で削除される", () => {
    const next = reduceActions({ zenn: "saving", note: "syncing" }, "zenn", null);
    expect(next).toEqual({ note: "syncing" });
  });

  it("expectedAction が現在の値と一致するとき削除される", () => {
    const next = reduceActions({ zenn: "saving" }, "zenn", null, "saving");
    expect(next).toEqual({});
  });

  it("expectedAction が現在の値と異なるときは prev のまま返す（後発を clobber しない）", () => {
    // 先発 saving の finally が、後発 syncing が走った後に呼ばれたケース
    const prev = { zenn: "syncing" } as const;
    const next = reduceActions(prev, "zenn", null, "saving");
    // 同一参照で返ることで、保持する syncing がクリアされない
    expect(next).toBe(prev);
    expect(next).toEqual({ zenn: "syncing" });
  });

  it("expectedAction 指定で対象プラットフォーム未登録なら何もしない", () => {
    const prev = { note: "saving" } as const;
    const next = reduceActions(prev, "zenn", null, "saving");
    expect(next).toBe(prev);
  });
});

describe("useBlogAccountManager", () => {
  // モック関数への参照を取得するために動的 import を使う
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let api: Record<string, any>;

  beforeEach(async () => {
    vi.clearAllMocks();
    api = await import("../../api");
    // デフォルトのモック戻り値を設定
    api.getBlogAccounts.mockResolvedValue([]);
    api.getBlogArticles.mockResolvedValue([]);
  });

  /** マウント時に getBlogAccounts が呼ばれること */
  it("マウント時に getBlogAccounts が呼ばれる", async () => {
    api.getBlogAccounts.mockResolvedValue([]);

    renderHook(() => useBlogAccountManager("all"));

    await waitFor(() => {
      expect(api.getBlogAccounts).toHaveBeenCalledTimes(1);
    });
  });

  /** アカウントが存在する場合は getBlogArticles も呼ばれること */
  it("アカウントが存在する場合 getBlogArticles も呼ばれる", async () => {
    api.getBlogAccounts.mockResolvedValue(dummyAccounts);
    api.getBlogArticles.mockResolvedValue(dummyArticles);

    const { result } = renderHook(() => useBlogAccountManager("all"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(api.getBlogArticles).toHaveBeenCalledTimes(1);
    expect(result.current.accounts).toEqual(dummyAccounts);
    expect(result.current.articles).toEqual(dummyArticles);
  });

  /** handleDelete を呼ぶと deleteBlogAccount が実行されデータが再取得されること */
  it("handleDelete を呼ぶと deleteBlogAccount が呼ばれデータが再取得される", async () => {
    api.getBlogAccounts.mockResolvedValue(dummyAccounts);
    api.getBlogArticles.mockResolvedValue(dummyArticles);
    api.deleteBlogAccount.mockResolvedValue(undefined);

    const { result } = renderHook(() => useBlogAccountManager("all"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // 削除後は accounts が空に
    api.getBlogAccounts.mockResolvedValue([]);

    await waitFor(async () => {
      await result.current.handleDelete("zenn");
    });

    expect(api.deleteBlogAccount).toHaveBeenCalledWith("acc-1");
    // 再取得が走ること
    await waitFor(() => {
      expect(api.getBlogAccounts).toHaveBeenCalledTimes(2);
    });
    expect(result.current.success).toBe("アカウントを解除しました");
  });

  /** getBlogAccounts がエラーの場合、accountError がセットされること */
  it("getBlogAccounts がエラーの場合 accountError がセットされる", async () => {
    api.getBlogAccounts.mockRejectedValue(new Error("ネットワークエラー"));

    const { result } = renderHook(() => useBlogAccountManager("all"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.accountError).toBe("ネットワークエラー");
  });

  /**
   * addBlogAccount と syncBlogAccount の両方が成功した場合、
   * 同期件数を含む success メッセージがセットされること
   */
  it("addBlogAccount 成功 + syncBlogAccount 成功の場合 synced_count を含む success がセットされる", async () => {
    api.getBlogAccounts
      .mockResolvedValueOnce([])
      .mockResolvedValue(dummyAccounts);
    api.getBlogArticles.mockResolvedValue(dummyArticles);
    api.addBlogAccount.mockResolvedValue(dummyAccounts[0]);
    api.syncBlogAccount.mockResolvedValue({ synced_count: 3, total_count: 5 });

    const { result } = renderHook(() => useBlogAccountManager("all"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      result.current.setDraftUsernames((prev) => ({ ...prev, zenn: "testuser" }));
    });

    await act(async () => {
      await result.current.handleSave("zenn");
    });

    expect(result.current.success).toBe("3件の記事を取得しました（合計: 5件）");
    expect(result.current.accountError).toBeNull();
  });

  /**
   * addBlogAccount が成功し syncBlogAccount が失敗した場合、
   * success と error の両方がセットされること（部分成功）
   */
  it("addBlogAccount 成功 + syncBlogAccount 失敗の場合 success と error が両方セットされる", async () => {
    api.getBlogAccounts
      .mockResolvedValueOnce([])
      .mockResolvedValue(dummyAccounts);
    api.getBlogArticles.mockResolvedValue(dummyArticles);
    api.addBlogAccount.mockResolvedValue(dummyAccounts[0]);
    api.syncBlogAccount.mockRejectedValue(new Error("同期に失敗しました"));

    const { result } = renderHook(() => useBlogAccountManager("all"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    await act(async () => {
      result.current.setDraftUsernames((prev) => ({ ...prev, zenn: "testuser" }));
    });

    await act(async () => {
      await result.current.handleSave("zenn");
    });

    // 連携成功メッセージが出ること
    expect(result.current.success).toBe("アカウントを連携しました");
    // 同期失敗エラーが accountError にセットされること
    expect(result.current.accountError).toBe("同期に失敗しました");
  });

  it("handleUpdate を呼ぶと updateBlogAccount が呼ばれ未同期状態に更新される", async () => {
    api.getBlogAccounts
      .mockResolvedValueOnce(dummyAccounts)
      .mockResolvedValueOnce([
        {
          ...dummyAccounts[0],
          username: "updated-user",
          last_synced_at: null,
        },
      ]);
    api.getBlogArticles
      .mockResolvedValueOnce(dummyArticles)
      .mockResolvedValueOnce([]);
    api.updateBlogAccount.mockResolvedValue({
      ...dummyAccounts[0],
      username: "updated-user",
      last_synced_at: null,
    });

    const { result } = renderHook(() => useBlogAccountManager("all"));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    let updated = false;
    await act(async () => {
      updated = await result.current.handleUpdate("zenn", "updated-user");
    });

    expect(updated).toBe(true);
    expect(api.updateBlogAccount).toHaveBeenCalledWith("zenn", "updated-user");
    await waitFor(() => {
      expect(result.current.accounts[0]?.username).toBe("updated-user");
    });
    expect(result.current.accounts[0]?.last_synced_at).toBeNull();
    expect(result.current.success).toBe("usernameを更新しました。再同期してください。");
  });
});
