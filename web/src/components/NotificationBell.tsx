import { useEffect, useRef } from "react";

import type { Notification } from "../api/notifications";
import { useNotifications } from "../hooks/useNotifications";
import { BellIcon } from "./icons/BellIcon";
import styles from "./NotificationBell.module.css";

/** 通知作成日時を相対表記に変換する（例: 3分前）。isoString はタイムゾーン付き（+09:00）を前提とする。 */
function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "たった今";
  if (minutes < 60) return `${minutes}分前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}時間前`;
  return `${Math.floor(hours / 24)}日前`;
}

function NotificationItem({
  notification,
  onRead,
}: {
  notification: Notification;
  onRead: (id: string) => void;
}) {
  return (
    <div
      className={`${styles.item} ${!notification.is_read ? styles.itemUnread : ""}`}
      onClick={() => !notification.is_read && onRead(notification.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && !notification.is_read && onRead(notification.id)}
    >
      <span
        className={`${styles.statusDot} ${notification.status === "completed" ? styles.statusDotCompleted : styles.statusDotFailed
          }`}
      />
      <div className={styles.itemBody}>
        <div className={styles.itemTitle}>{notification.title}</div>
        <div className={styles.itemTime}>{formatRelativeTime(notification.created_at)}</div>
      </div>
      {!notification.is_read && <span className={styles.unreadDot} />}
    </div>
  );
}

/**
 * サイドバーに配置する通知ベルコンポーネント。
 * 30秒ごとに未読件数をポーリングし、クリック時に通知パネルを開く。
 */
export function NotificationBell() {
  const { notifications, unreadCount, isOpen, isLoading, openPanel, closePanel, markAsRead, markAllAsRead } =
    useNotifications();
  const ref = useRef<HTMLDivElement>(null);

  // パネル外クリックで閉じる
  useEffect(() => {
    if (!isOpen) return;
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        closePanel();
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [isOpen, closePanel]);

  return (
    <div className={styles.wrapper} ref={ref}>
      {isOpen && (
        <div className={styles.panel}>
          <div className={styles.panelHeader}>
            <span className={styles.panelTitle}>通知</span>
            {unreadCount > 0 && (
              <button type="button" className={styles.markAllBtn} onClick={markAllAsRead}>
                全て既読
              </button>
            )}
          </div>
          <div className={styles.list}>
            {isLoading && notifications.length === 0 ? (
              <div className={styles.empty}>読み込み中...</div>
            ) : notifications.length === 0 ? (
              <div className={styles.empty}>通知はありません</div>
            ) : (
              notifications.map((n) => (
                <NotificationItem key={n.id} notification={n} onRead={markAsRead} />
              ))
            )}
          </div>
        </div>
      )}
      <button
        type="button"
        className={styles.trigger}
        onClick={isOpen ? closePanel : openPanel}
        aria-label={`通知${unreadCount > 0 ? `（未読${unreadCount}件）` : ""}`}
      >
        <span className={styles.triggerInner}>
          <span className={styles.bellIcon}>
            <BellIcon className={styles.bellIconSvg} />
          </span>
          <span className={styles.label}>通知</span>
        </span>
        {unreadCount > 0 && (
          <span className={styles.badge}>{unreadCount > 99 ? "99+" : unreadCount}</span>
        )}
      </button>
    </div>
  );
}
