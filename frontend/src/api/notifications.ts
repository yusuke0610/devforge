import { request } from "./client";
import { PATHS } from "./paths";
import type {
  MarkAllReadResponse,
  NotificationResponse,
  UnreadCountResponse,
} from "./types";

export type { UnreadCountResponse } from "./types";

/**
 * 通知 1 件の型。DTO の正本は backend `routers/notifications.py:NotificationResponse`
 * （OpenAPI 経由で `api/types.ts` に再エクスポート、ADR-0007）。
 * 呼び出し側の歴史的な `Notification` 名を保つためのエイリアス。
 */
export type Notification = NotificationResponse;

/**
 * 最新30件の通知を取得します。
 */
export function getNotifications(): Promise<NotificationResponse[]> {
  return request<NotificationResponse[]>(PATHS.notifications.base);
}

/**
 * 未読件数を取得します。
 */
export function getUnreadCount(): Promise<UnreadCountResponse> {
  return request<UnreadCountResponse>(PATHS.notifications.unreadCount);
}

/**
 * 指定された通知を既読にします。
 */
export function markAsRead(notificationId: string): Promise<NotificationResponse> {
  return request<NotificationResponse>(PATHS.notifications.read(notificationId), {
    method: "PATCH",
  });
}

/**
 * 全通知を既読にします。
 */
export function markAllAsRead(): Promise<MarkAllReadResponse> {
  return request<MarkAllReadResponse>(PATHS.notifications.readAll, {
    method: "POST",
  });
}
