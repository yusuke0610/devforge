import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useNotifications } from "./useNotifications";
import type { Notification } from "../api/notifications";
import { logger } from "../utils/logger";

vi.mock("../api/notifications", () => ({
  getNotifications: vi.fn(),
  getUnreadCount: vi.fn(),
  markAsRead: vi.fn(),
  markAllAsRead: vi.fn(),
}));

const dummyNotifications: Notification[] = [
  { id: "n-1", task_type: "analysis", status: "completed", title: "通知1", message: "内容1", is_read: false, created_at: "2024-01-01T00:00:00" },
  { id: "n-2", task_type: "analysis", status: "completed", title: "通知2", message: "内容2", is_read: false, created_at: "2024-01-02T00:00:00" },
];

describe("useNotifications", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let api: Record<string, any>;

  beforeEach(async () => {
    vi.clearAllMocks();
    api = await import("../api/notifications");
    api.getUnreadCount.mockResolvedValue({ count: 0 });
    api.getNotifications.mockResolvedValue([]);
    api.markAsRead.mockResolvedValue({ id: "n-1", is_read: true });
    api.markAllAsRead.mockResolvedValue({ updated: 2 });
    vi.spyOn(logger, "warn").mockImplementation(() => {});
  });

  /** openPanel を呼ぶと getNotifications が実行され未読通知のみ表示されること */
  it("openPanel を呼ぶと未読通知のみ notifications にセットされる", async () => {
    api.getNotifications.mockResolvedValue([
      ...dummyNotifications,
      { id: "n-3", task_type: "analysis", status: "completed", title: "既読", message: "既読内容", is_read: true, created_at: "2024-01-03T00:00:00" },
    ]);

    const { result } = renderHook(() => useNotifications());

    await act(async () => {
      result.current.openPanel();
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.notifications).toHaveLength(2);
    expect(result.current.notifications.every((n) => !n.is_read)).toBe(true);
    expect(result.current.isOpen).toBe(true);
  });

  /** handleMarkAllAsRead を呼ぶと markAllAsRead が実行され unreadCount が 0 になること */
  it("markAllAsRead を呼ぶと unreadCount が 0 になる", async () => {
    api.getNotifications.mockResolvedValue(dummyNotifications);

    const { result } = renderHook(() => useNotifications());

    await act(async () => {
      result.current.openPanel();
    });

    await waitFor(() => {
      expect(result.current.unreadCount).toBe(2);
    });

    await act(async () => {
      await result.current.markAllAsRead();
    });

    expect(api.markAllAsRead).toHaveBeenCalledTimes(1);
    expect(result.current.unreadCount).toBe(0);
  });

  /** 初回ポーリング（getUnreadCount）が失敗しても unreadCount は初期値のまま、かつ logger.warn が呼ばれる */
  it("getUnreadCount が失敗すると unreadCount は 0 のまま据え置かれ logger.warn が呼ばれる", async () => {
    const apiError = new Error("network error");
    api.getUnreadCount.mockRejectedValue(apiError);

    const { result } = renderHook(() => useNotifications());

    await waitFor(() => {
      expect(logger.warn).toHaveBeenCalledWith(
        "未読通知件数の取得に失敗しました",
        apiError,
      );
    });

    expect(result.current.unreadCount).toBe(0);
  });

  /** openPanel 中の getNotifications が失敗しても notifications は空のまま、isLoading は false に戻り logger.warn が呼ばれる */
  it("getNotifications が失敗すると notifications は空のまま isLoading が false に戻り logger.warn が呼ばれる", async () => {
    const apiError = new Error("network error");
    api.getNotifications.mockRejectedValue(apiError);

    const { result } = renderHook(() => useNotifications());

    await act(async () => {
      result.current.openPanel();
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.notifications).toEqual([]);
    expect(logger.warn).toHaveBeenCalledWith(
      "通知一覧の取得に失敗しました",
      apiError,
    );
  });

  /** markAsRead が失敗しても notifications / unreadCount は変化せず logger.warn が呼ばれる */
  it("markAsRead が失敗すると state は変化せず logger.warn が呼ばれる", async () => {
    api.getNotifications.mockResolvedValue(dummyNotifications);

    const { result } = renderHook(() => useNotifications());

    await act(async () => {
      result.current.openPanel();
    });

    await waitFor(() => {
      expect(result.current.unreadCount).toBe(2);
    });

    const apiError = new Error("network error");
    api.markAsRead.mockRejectedValue(apiError);

    await act(async () => {
      await result.current.markAsRead("n-1");
    });

    expect(result.current.notifications.find((n) => n.id === "n-1")?.is_read).toBe(false);
    expect(result.current.unreadCount).toBe(2);
    expect(logger.warn).toHaveBeenCalledWith(
      "通知の既読化に失敗しました",
      apiError,
    );
  });

  /** markAllAsRead が失敗しても notifications / unreadCount は変化せず logger.warn が呼ばれる */
  it("markAllAsRead が失敗すると state は変化せず logger.warn が呼ばれる", async () => {
    api.getNotifications.mockResolvedValue(dummyNotifications);

    const { result } = renderHook(() => useNotifications());

    await act(async () => {
      result.current.openPanel();
    });

    await waitFor(() => {
      expect(result.current.unreadCount).toBe(2);
    });

    const apiError = new Error("network error");
    api.markAllAsRead.mockRejectedValue(apiError);

    await act(async () => {
      await result.current.markAllAsRead();
    });

    expect(result.current.unreadCount).toBe(2);
    expect(result.current.notifications.every((n) => !n.is_read)).toBe(true);
    expect(logger.warn).toHaveBeenCalledWith(
      "通知の一括既読化に失敗しました",
      apiError,
    );
  });
});
