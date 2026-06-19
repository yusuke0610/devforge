import { useEffect, useRef, useState } from "react";

import {
  AGENT_MODEL_MESSAGES,
  AUTH_PROMPT_MESSAGES,
  BILLING_PAGE_MESSAGES,
  EXTERNAL_LINKS,
  UI_MESSAGES,
} from "../constants/messages";
import type { Theme } from "../hooks/useTheme";
import { GitHubMarkIcon } from "./icons/GitHubMarkIcon";
import styles from "./UserMenu.module.css";

/**
 * サイドバーフッターのユーザーメニュー。
 * 認証済み: ユーザー名トリガー（押下でメニュー開閉）+ ダークモード / ログアウト / Issue報告 / コピーライト。
 * 未認証: ユーザー名位置に「ログイン」ボタン（押下で OAuth 開始）+ 右に ▲ チェブロン（押下でメニュー開閉）。
 *   メニューはダークモード / Issue報告 / コピーライト（ログアウト/ログイン項目は出さない）。
 */
export function UserMenu({
  isAuthenticated,
  username,
  theme,
  onToggleTheme,
  onLogout,
  onLogin,
  onOpenModelSelect,
  onOpenBilling,
}: {
  isAuthenticated: boolean;
  username: string | null;
  theme: Theme;
  onToggleTheme: () => void;
  onLogout: () => void;
  onLogin: () => void;
  /** AI モデル選択モーダルを開く（認証済みのみ表示 / ADR-0012）。 */
  onOpenModelSelect?: () => void;
  /** トークン購入画面へ遷移する（認証済みのみ表示。モデル切り替えとは分離 / ADR-0012）。 */
  onOpenBilling?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  const isDark = theme === "dark";

  return (
    <div className={styles.wrapper} ref={ref}>
      {open && (
        <div className={styles.menu}>
          <button type="button" className={styles.menuItem} onClick={onToggleTheme}>
            <span className={styles.menuItemLabel}>{UI_MESSAGES.DARK_MODE}</span>
            <span className={`${styles.toggle} ${isDark ? styles.toggleOn : ""}`}>
              <span className={styles.toggleKnob} />
            </span>
          </button>
          <div className={styles.separator} />
          {/* AI モデル切り替えは認証済みのみ（モデル選択はログインユーザーの設定 / ADR-0012）。 */}
          {isAuthenticated && onOpenModelSelect && (
            <button
              type="button"
              className={styles.menuItem}
              onClick={() => {
                setOpen(false);
                onOpenModelSelect();
              }}
            >
              <span className={styles.menuItemLabel}>{AGENT_MODEL_MESSAGES.MENU_ITEM}</span>
            </button>
          )}
          {/* トークン購入はモデル切り替えとは別項目（購入と切り替えを分離 / ADR-0012）。 */}
          {isAuthenticated && onOpenBilling && (
            <button
              type="button"
              className={styles.menuItem}
              onClick={() => {
                setOpen(false);
                onOpenBilling();
              }}
            >
              <span className={styles.menuItemLabel}>{BILLING_PAGE_MESSAGES.MENU_ITEM}</span>
            </button>
          )}
          {(onOpenModelSelect || onOpenBilling) && isAuthenticated && (
            <div className={styles.separator} />
          )}
          {/* 未認証ではログインはトリガー側のボタンに集約するため、メニューには出さない。 */}
          {isAuthenticated && (
            <>
              <button
                type="button"
                className={`${styles.menuItem} ${styles.logoutItem}`}
                onClick={onLogout}
              >
                <span className={styles.menuItemLabel}>{UI_MESSAGES.LOGOUT}</span>
              </button>
              <div className={styles.separator} />
            </>
          )}
          <a
            className={styles.menuItem}
            href={EXTERNAL_LINKS.ISSUE_REPORT}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setOpen(false)}
          >
            <span className={styles.menuItemLabel}>{UI_MESSAGES.REPORT_ISSUE}</span>
            <svg
              className={styles.externalIcon}
              viewBox="0 0 24 24"
              width="14"
              height="14"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
              focusable="false"
            >
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
              <polyline points="15 3 21 3 21 9" />
              <line x1="10" y1="14" x2="21" y2="3" />
            </svg>
            <span className={styles.srOnly}>{UI_MESSAGES.OPENS_IN_NEW_TAB}</span>
          </a>
          <div className={styles.menuFooter}>{UI_MESSAGES.COPYRIGHT}</div>
        </div>
      )}
      {isAuthenticated ? (
        <button type="button" className={styles.trigger} onClick={() => setOpen(!open)}>
          <span className={styles.triggerName}>{username || UI_MESSAGES.MENU_FALLBACK}</span>
          <span className={styles.triggerChevron}>&#x25B2;</span>
        </button>
      ) : (
        // 未認証: ユーザー名位置にログインボタン、右に ▲（メニュー開閉）。
        <div className={styles.guestTrigger}>
          <button type="button" className={styles.loginButton} onClick={onLogin}>
            <GitHubMarkIcon className={styles.loginIcon} />
            {AUTH_PROMPT_MESSAGES.SIDEBAR_LOGIN}
          </button>
          <button
            type="button"
            className={styles.guestChevron}
            aria-label={UI_MESSAGES.FOOTER_MENU}
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            &#x25B2;
          </button>
        </div>
      )}
    </div>
  );
}
