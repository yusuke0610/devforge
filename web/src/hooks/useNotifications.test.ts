import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useNotifications } from "./useNotifications";
import type { Notification } from "../api/notifications";

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
});
