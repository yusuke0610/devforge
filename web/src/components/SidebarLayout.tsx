import { useState } from "react";
import type { ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { initiateGitHubLogin } from "../api";
import type { AuthUser } from "../router/guards";
import type { Theme } from "../hooks/useTheme";
import { AUTH_PROMPT_MESSAGES, UI_MESSAGES } from "../constants/messages";
import { NotificationBell } from "./NotificationBell";
import { UserMenu } from "./UserMenu";
import { AgentModelBadge } from "./agent/AgentModelBadge";
import { ModelSelectModal } from "./agent/ModelSelectModal";
import { useLoginPrompt } from "./auth/loginPromptContext";
import { ChevronDownIcon } from "./icons/ChevronDownIcon";
import shared from "../styles/shared.module.css";
import styles from "../App.module.css";

/**
 * サイドバー付きの共通レイアウト。認証状態に応じて中身を出し分ける。
 *
 * - 認証済み (`user` 非 null): 全ナビゲーションを活性化し、フッターに通知ベル + ユーザーメニュー。
 *   レイアウトルートとして使う場合は `children` を渡さず `<Outlet />` を描画する。
 * - 未認証 (`user` === null): 職務経歴書のお試し入力のみ可能。GitHub連携は
 *   表示するが、押下するとログイン促進モーダルを開く。フッターはユーザーメニュー（ログインモード）で、
 *   トリガーが「ログイン」、メニューにダークモード / ログイン / Issue報告 / 著作権表示を出す
 *   （通知ベルは出さない）。
 */
export function SidebarLayout({
  user,
  theme,
  onToggleTheme,
  onLogout,
  children,
}: {
  user: AuthUser | null;
  theme: Theme;
  onToggleTheme: () => void;
  onLogout: () => void;
  children?: ReactNode;
}) {
  const navigate = useNavigate();
  const requestLogin = useLoginPrompt();
  // GitHub 連携オプション（フォーク含む）の開閉とチェック状態。
  const [githubOptionsOpen, setGithubOptionsOpen] = useState(false);
  const [includeForks, setIncludeForks] = useState(false);
  // サイドバーの折りたたみ状態。折りたたむと本文領域が全幅に広がる。
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  // AI モデル選択モーダルの開閉（UserMenu から開く / ADR-0012）。
  const [modelSelectOpen, setModelSelectOpen] = useState(false);

  const isAuthenticated = user !== null;

  /**
   * GitHub 連携を実行する。
   * 連携 API のトリガーはサブパネル内の「連携実行」ボタンのみ。
   * サイドバー項目のクリックは画面遷移に徹し、連携リクエストは飛ばさない
   * （不要なリクエストの温床になるため）。
   * 実行意図を runNonce としてページへ渡し、ダッシュボード側で
   * 連携実行（ポーリング）とエラー表示を担わせる。
   */
  const triggerGitHubLink = () => {
    navigate("/github_link", {
      state: { runNonce: Date.now(), includeForks },
    });
  };

  const handleLogin = () => {
    void initiateGitHubLogin(window.location.origin);
  };

  return (
    <div className={shared.page}>
      <div
        className={`${styles.appLayout} ${sidebarCollapsed ? styles.sidebarCollapsed : ""}`}
      >
        {/* 折りたたみ中のみ表示する、サイドバーを再展開するための固定ボタン。 */}
        {sidebarCollapsed && (
          <button
            type="button"
            className={styles.sidebarOpenButton}
            aria-label={UI_MESSAGES.SIDEBAR_EXPAND}
            onClick={() => setSidebarCollapsed(false)}
          >
            »
          </button>
        )}
        <aside className={styles.sidebar} aria-hidden={sidebarCollapsed}>
          <div className={styles.sidebarHeader}>
            <p className={styles.sidebarTitle}>DevForge</p>
            <button
              type="button"
              className={styles.sidebarCollapseButton}
              aria-label={UI_MESSAGES.SIDEBAR_COLLAPSE}
              onClick={() => setSidebarCollapsed(true)}
            >
              «
            </button>
          </div>
          <nav className={styles.sidebarNav}>
            <NavLink
              to="/career"
              className={({ isActive }) =>
                `${styles.sidebarItem} ${isActive ? styles.active : ""}`
              }
            >
              {UI_MESSAGES.NAV_CAREER}
            </NavLink>

            {/* GitHub連携: 認証済みかつ GitHub ユーザーのみ活性。未認証は押下でログインを促す。 */}
            {isAuthenticated ? (
              user.isGitHubUser && (
                <div className={styles.sidebarItemGroup}>
                  <div className={styles.sidebarItemRow}>
                    <NavLink
                      to="/github_link"
                      className={({ isActive }) =>
                        `${styles.sidebarItem} ${isActive ? styles.active : ""}`
                      }
                    >
                      {UI_MESSAGES.NAV_GITHUB_LINK}
                    </NavLink>
                    <button
                      type="button"
                      className={styles.sidebarChevron}
                      aria-label={UI_MESSAGES.GITHUB_LINK_OPTIONS}
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
                      <button
                        type="button"
                        className={styles.sidebarItem}
                        onClick={triggerGitHubLink}
                      >
                        {UI_MESSAGES.GITHUB_LINK_RUN}
                      </button>
                      <label className={styles.sidebarCheckbox}>
                        <input
                          type="checkbox"
                          checked={includeForks}
                          onChange={(e) => setIncludeForks(e.target.checked)}
                        />
                        {UI_MESSAGES.GITHUB_INCLUDE_FORKS}
                      </label>
                    </div>
                  )}
                </div>
              )
            ) : (
              <button
                type="button"
                className={styles.sidebarItem}
                onClick={requestLogin}
                title={AUTH_PROMPT_MESSAGES.LOGIN_REQUIRED_HINT}
              >
                {UI_MESSAGES.NAV_GITHUB_LINK}
              </button>
            )}
          </nav>
          <div className={styles.sidebarFooter}>
            {/* AI ステータス（使用モデル）は認証済みのみ表示。 */}
            {isAuthenticated && <AgentModelBadge />}
            {/* 通知ベルは認証済みのみ（未認証はポーリングで 401 を連発しないよう出さない）。 */}
            {isAuthenticated && <NotificationBell />}
            <UserMenu
              isAuthenticated={isAuthenticated}
              username={user?.username ?? null}
              theme={theme}
              onToggleTheme={onToggleTheme}
              onLogout={onLogout}
              onLogin={handleLogin}
              onOpenModelSelect={isAuthenticated ? () => setModelSelectOpen(true) : undefined}
            />
          </div>
        </aside>

        <main className={styles.mainContent}>{children ?? <Outlet />}</main>
      </div>
      {isAuthenticated && modelSelectOpen && (
        <ModelSelectModal onClose={() => setModelSelectOpen(false)} />
      )}
    </div>
  );
}
