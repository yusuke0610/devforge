import { useState, useEffect, useCallback, useRef } from "react";

import {
  getNotifications,
  getUnreadCount,
  markAsRead,
  markAllAsRead,
  type Notification,
} from "../api/notifications";
import { logger } from "../utils/logger";

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
    } catch (error) {
      // ポーリングエラーは UI をブロックしないためサイレントに無視するが、
      // 障害調査のためログだけは残す。
      logger.warn("未読通知件数の取得に失敗しました", error);
    }
  }, []);

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getNotifications();
      // パネルを開く時点では未読のみを表示する（既読は非表示）
      setNotifications(data.filter((n) => !n.is_read));
      setUnreadCount(data.filter((n) => !n.is_read).length);
    } catch (error) {
      // パネル表示中のエラーは通知一覧を空のまま維持するが、ログは残す。
      logger.warn("通知一覧の取得に失敗しました", error);
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
    } catch (error) {
      // 既読化に失敗しても UI 上は据え置くが、ログは残す。
      logger.warn("通知の既読化に失敗しました", error);
    }
  }, []);

  const handleMarkAllAsRead = useCallback(async () => {
    try {
      await markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (error) {
      // 一括既読化に失敗しても UI 上は据え置くが、ログは残す。
      logger.warn("通知の一括既読化に失敗しました", error);
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
