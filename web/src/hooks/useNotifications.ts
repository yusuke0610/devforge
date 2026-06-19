import { useState, useEffect, useCallback, useRef } from "react";

import {
  getNotifications,
  getUnreadCount,
  markAsRead,
  markAllAsRead,
  type Notification,
} from "../api/notifications";

const POLL_INTERVAL_MS = 30_000;

/**
 * 通知の取得・既読管理を行うフック。
 * 30秒ごとに未読件数をポーリングし、ベルマークのバッジを更新する。
 */
export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const intervalRef = useRef<number | null>(null);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const { count } = await getUnreadCount();
      setUnreadCount(count);
    } catch {
      // ポーリングエラーはサイレントに無視する
    }
  }, []);

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getNotifications();
      // パネルを開く時点では未読のみを表示する（既読は非表示）
      setNotifications(data.filter((n) => !n.is_read));
      setUnreadCount(data.filter((n) => !n.is_read).length);
    } catch {
      // エラーは無視
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 初回ロードと定期ポーリング
  useEffect(() => {
    fetchUnreadCount();
    intervalRef.current = window.setInterval(fetchUnreadCount, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchUnreadCount]);

  const openPanel = useCallback(() => {
    setIsOpen(true);
    fetchNotifications();
  }, [fetchNotifications]);

  const closePanel = useCallback(() => {
    setIsOpen(false);
  }, []);

  const handleMarkAsRead = useCallback(async (id: string) => {
    try {
      await markAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // エラーは無視
    }
  }, []);

  const handleMarkAllAsRead = useCallback(async () => {
    try {
      await markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {
      // エラーは無視
    }
  }, []);

  return {
    notifications,
    unreadCount,
    isOpen,
    isLoading,
    openPanel,
    closePanel,
    markAsRead: handleMarkAsRead,
    markAllAsRead: handleMarkAllAsRead,
  };
}
