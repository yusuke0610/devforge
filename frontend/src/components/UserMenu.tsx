import { useEffect, useRef, useState } from "react";

import { EXTERNAL_LINKS, UI_MESSAGES } from "../constants/messages";
import type { Theme } from "../hooks/useTheme";
import styles from "./UserMenu.module.css";

export function UserMenu({
  username,
  theme,
  onToggleTheme,
  onLogout,
}: {
  username: string | null;
  theme: Theme;
  onToggleTheme: () => void;
  onLogout: () => void;
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
            <span className={styles.menuItemLabel}>ダークモード</span>
            <span className={`${styles.toggle} ${isDark ? styles.toggleOn : ""}`}>
              <span className={styles.toggleKnob} />
            </span>
          </button>
          <div className={styles.separator} />
          <button
            type="button"
            className={`${styles.menuItem} ${styles.logoutItem}`}
            onClick={onLogout}
          >
            <span className={styles.menuItemLabel}>ログアウト</span>
          </button>
          <div className={styles.separator} />
          <a
            className={styles.menuItem}
            href={EXTERNAL_LINKS.ISSUE_REPORT}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setOpen(false)}
          >
            <span className={styles.menuItemLabel}>{UI_MESSAGES.REPORT_ISSUE}</span>
          </a>
          <div className={styles.menuFooter}>{UI_MESSAGES.COPYRIGHT}</div>
        </div>
      )}
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setOpen(!open)}
      >
        <span className={styles.triggerName}>{username || "Menu"}</span>
        <span className={styles.triggerChevron}>&#x25B2;</span>
      </button>
    </div>
  );
}
