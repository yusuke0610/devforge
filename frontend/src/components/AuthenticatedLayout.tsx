import { NavLink, Outlet } from "react-router-dom";

import type { AuthUser } from "../router/guards";
import type { Theme } from "../hooks/useTheme";
import { NotificationBell } from "./NotificationBell";
import { UserMenu } from "./UserMenu";
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
              <NavLink
                to="/github_intelligence"
                className={({ isActive }) =>
                  `${styles.sidebarItem} ${isActive ? styles.active : ""}`
                }
              >
                GitHub分析
              </NavLink>
            )}
            <NavLink
              to="/blog"
              className={({ isActive }) =>
                `${styles.sidebarItem} ${isActive ? styles.active : ""}`
              }
            >
              ブログ連携
            </NavLink>
            <NavLink
              to="/career_analysis"
              className={({ isActive }) =>
                `${styles.sidebarItem} ${isActive ? styles.active : ""}`
              }
            >
              キャリア分析
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
