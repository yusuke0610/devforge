import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { MemoryRouter } from "react-router-dom";

import { useAuthSession } from "./useAuthSession";

/** ../api 全体をモック */
vi.mock("../api", () => ({
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
  setOnUnauthorized: vi.fn(),
}));

/** MemoryRouter でラップする wrapper を生成する */
function makeWrapper(initialPath: string) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(MemoryRouter, { initialEntries: [initialPath] }, children);
  };
}

describe("useAuthSession", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let api: Record<string, any>;

  beforeEach(async () => {
    vi.clearAllMocks();
    sessionStorage.clear();
    api = await import("../api");
  });

  /** sessionStorage に保存された user が初期値として復元されること */
  it("sessionStorage に user があれば初期値として復元する", () => {
    sessionStorage.setItem(
      "auth_user",
      JSON.stringify({ username: "saved-user", isGitHubUser: true }),
    );

    const { result } = renderHook(() => useAuthSession(), {
      wrapper: makeWrapper("/career"),
    });

    expect(result.current.user).toEqual({ username: "saved-user", isGitHubUser: true });
    // 既に user があるので getCurrentUser は呼ばれない
    expect(api.getCurrentUser).not.toHaveBeenCalled();
  });

  /** 公開パス（/login）では user=null でも authLoading=false が初期値であること */
  it("公開パスでは user=null でも authLoading=false で getCurrentUser を呼ばない", async () => {
    const { result } = renderHook(() => useAuthSession(), {
      wrapper: makeWrapper("/login"),
    });

    await waitFor(() => {
      expect(result.current.authLoading).toBe(false);
    });
    expect(api.getCurrentUser).not.toHaveBeenCalled();
  });

  /** 保護パスで user=null なら getCurrentUser でセッション復元を試みる */
  it("保護パスで user=null なら getCurrentUser を呼んでセッション復元する", async () => {
    api.getCurrentUser.mockResolvedValue({
      username: "fetched-user",
      is_github_user: false,
    });

    const { result } = renderHook(() => useAuthSession(), {
      wrapper: makeWrapper("/career"),
    });

    await waitFor(() => {
      expect(result.current.user).toEqual({
        username: "fetched-user",
        isGitHubUser: false,
      });
    });

    // sessionStorage にも書き戻されること
    const stored = sessionStorage.getItem("auth_user");
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored as string);
    expect(parsed).toEqual({ username: "fetched-user", isGitHubUser: false });
  });

  /**
   * handleLogout 後は justLoggedOut ref が立ち、後続の effect で getCurrentUser を呼ばないこと。
   * 「ログアウト直後にセッション復元が走って一瞬ログイン状態が復活する」race を直接守る。
   */
  it("handleLogout 後に getCurrentUser が呼ばれない（race 防止）", async () => {
    sessionStorage.setItem(
      "auth_user",
      JSON.stringify({ username: "active-user", isGitHubUser: true }),
    );
    api.logout.mockResolvedValue(undefined);
    api.getCurrentUser.mockResolvedValue({
      username: "should-not-be-restored",
      is_github_user: true,
    });

    const { result } = renderHook(() => useAuthSession(), {
      wrapper: makeWrapper("/career"),
    });

    await waitFor(() => {
      expect(result.current.user).not.toBeNull();
    });

    await act(async () => {
      await result.current.handleLogout();
    });

    // user は null に
    expect(result.current.user).toBeNull();
    // sessionStorage もクリア
    expect(sessionStorage.getItem("auth_user")).toBeNull();
    // ログアウト後の effect で getCurrentUser が走らないこと（race 防止）
    await waitFor(() => {
      expect(result.current.authLoading).toBe(false);
    });
    expect(api.getCurrentUser).not.toHaveBeenCalled();
  });

  /** handleLoginSuccess で user state と sessionStorage が両方更新されること */
  it("handleLoginSuccess で user と sessionStorage が更新される", async () => {
    const { result } = renderHook(() => useAuthSession(), {
      wrapper: makeWrapper("/login"),
    });

    await waitFor(() => {
      expect(result.current.authLoading).toBe(false);
    });

    act(() => {
      result.current.handleLoginSuccess({
        username: "new-user",
        is_github_user: true,
      });
    });

    expect(result.current.user).toEqual({ username: "new-user", isGitHubUser: true });
    const stored = JSON.parse(sessionStorage.getItem("auth_user") as string);
    expect(stored).toEqual({ username: "new-user", isGitHubUser: true });
  });
});
