import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import type { AuthUser } from "../router/guards";
import type { Theme } from "../hooks/useTheme";
import { NotificationBell } from "./NotificationBell";
import { UserMenu } from "./UserMenu";
import { ChevronDownIcon } from "./icons/ChevronDownIcon";
import shared from "../styles/shared.module.css";
import styles from "../App.module.css";

/**
 * 認証済みユーザー向けのサイドバー付きレイアウト。
 * PrivateRoute でガードされた後にのみレンダリングされるため、user は非 null。
 */
export function AuthenticatedLayout({
  user,
  theme,
  onToggleTheme,
  onLogout,
}: {
  user: AuthUser;
  theme: Theme;
  onToggleTheme: () => void;
  onLogout: () => void;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  // GitHub 連携オプション（フォーク含む）の開閉とチェック状態。
  const [githubOptionsOpen, setGithubOptionsOpen] = useState(false);
  const [includeForks, setIncludeForks] = useState(false);

  /**
   * GitHub 連携を実行する。
   * 連携 API のトリガーはこのサイドバークリックのみ。
   * 実行意図を runNonce としてページへ渡し、ダッシュボード側で
   * 連携実行（ポーリング）とエラー表示を担わせる。
   */
  const triggerGitHubLink = () => {
    navigate("/github_link", {
      state: { runNonce: Date.now(), includeForks },
    });
  };

  const githubActive = location.pathname === "/github_link";

  return (
    <div className={shared.page}>
      <div className={styles.appLayout}>
        <aside className={styles.sidebar}>
          <p className={styles.sidebarTitle}>DevForge</p>
          <nav className={styles.sidebarNav}>
            <NavLink
              to="/career"
              className={({ isActive }) =>
                `${styles.sidebarItem} ${isActive ? styles.active : ""}`
              }
            >
              職務経歴書
            </NavLink>
            {user.isGitHubUser && (
              <div className={styles.sidebarItemGroup}>
                <div className={styles.sidebarItemRow}>
                  <button
                    type="button"
                    className={`${styles.sidebarItem} ${githubActive ? styles.active : ""}`}
                    onClick={triggerGitHubLink}
                  >
                    GitHub連携
                  </button>
                  <button
                    type="button"
                    className={styles.sidebarChevron}
                    aria-label="GitHub連携オプション"
                    aria-expanded={githubOptionsOpen}
                    onClick={() => setGithubOptionsOpen((open) => !open)}
                  >
                    <ChevronDownIcon
                      className={githubOptionsOpen ? styles.chevronOpen : undefined}
                    />
                  </button>
                </div>
                {githubOptionsOpen && (
                  <div className={styles.sidebarSubPanel}>
                    <label className={styles.sidebarCheckbox}>
                      <input
                        type="checkbox"
                        checked={includeForks}
                        onChange={(e) => setIncludeForks(e.target.checked)}
                      />
                      フォークしたリポジトリを含む
                    </label>
                  </div>
                )}
              </div>
            )}
            <NavLink
              to="/blog"
              className={({ isActive }) =>
                `${styles.sidebarItem} ${isActive ? styles.active : ""}`
              }
            >
              ブログ連携
            </NavLink>
          </nav>
          <div className={styles.sidebarFooter}>
            <NotificationBell />
            <UserMenu
              username={user.username}
              theme={theme}
              onToggleTheme={onToggleTheme}
              onLogout={onLogout}
            />
          </div>
        </aside>

        <main className={styles.mainContent}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
