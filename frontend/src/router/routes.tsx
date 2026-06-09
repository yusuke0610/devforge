import { Route, Routes, Navigate } from "react-router-dom";

import type { Theme } from "../hooks/useTheme";
import { SidebarLayout } from "../components/SidebarLayout";
import { LoadingOverlay } from "../components/LoadingOverlay";
import { PrivateRoute, PublicRoute, type AuthUser } from "./guards";
import CareerPage from "../pages/CareerPage";
import GitHubLinkPage from "../pages/GitHubLinkPage";
import BlogPage from "../pages/BlogPage";
import GitHubCallbackPage from "../pages/GitHubCallbackPage";
import LoginPage from "../pages/LoginPage";
import NotFoundPage from "../pages/NotFoundPage";

type AppRoutesProps = {
  user: AuthUser | null;
  authLoading: boolean;
  theme: Theme;
  onToggleTheme: () => void;
  githubError: string | null;
  onLogout: () => void;
  onLoginSuccess: (user: { username: string; is_github_user: boolean }) => void;
};

/**
 * `/career` を認証有無の両対応にするディスパッチャ。
 * - 認証判定中: LoadingOverlay（認証状態確定前のちらつきを防ぐ）
 * - それ以外: 共通の SidebarLayout を描画。未認証時は連携メニューを非活性にし、
 *   フッターにログインボタンを出す（SidebarLayout が user の有無で出し分ける）。
 */
function CareerRoute({
  user,
  authLoading,
  theme,
  onToggleTheme,
  onLogout,
}: {
  user: AuthUser | null;
  authLoading: boolean;
  theme: Theme;
  onToggleTheme: () => void;
  onLogout: () => void;
}) {
  if (authLoading) return <LoadingOverlay />;
  return (
    <SidebarLayout
      user={user}
      theme={theme}
      onToggleTheme={onToggleTheme}
      onLogout={onLogout}
    >
      <CareerPage isAuthenticated={user !== null} />
    </SidebarLayout>
  );
}

/**
 * アプリケーション全体のルート定義。
 * パスとページコンポーネントの対応を管理する。
 */
export default function AppRoutes({
  user,
  authLoading,
  theme,
  onToggleTheme,
  githubError,
  onLogout,
  onLoginSuccess,
}: AppRoutesProps) {
  return (
    <Routes>
      {/* 未認証ルート */}
      <Route element={<PublicRoute user={user} authLoading={authLoading} />}>
        <Route path="/login" element={<LoginPage githubError={githubError} />} />
      </Route>

      {/* 職務経歴書: 認証有無の両対応（未ログインはお試し入力、保存時にログインを促す） */}
      <Route
        path="/career"
        element={
          <CareerRoute
            user={user}
            authLoading={authLoading}
            theme={theme}
            onToggleTheme={onToggleTheme}
            onLogout={onLogout}
          />
        }
      />

      {/* 認証済み専用ルート（GitHub連携・ブログ連携） */}
      <Route element={<PrivateRoute user={user} authLoading={authLoading} />}>
        <Route
          element={
            <SidebarLayout
              user={user!}
              theme={theme}
              onToggleTheme={onToggleTheme}
              onLogout={onLogout}
            />
          }
        >
          <Route path="/github_link" element={<GitHubLinkPage />} />
          <Route path="/blog" element={<BlogPage />} />
        </Route>
      </Route>

      {/*
        GitHub OAuth コールバック: Cloudflare Pages の /auth/** プロキシに巻き込まれないよう、
        SPA ルートの /github/callback で React が受け取り、POST で認証を完了する。
      */}
      <Route
        path="/github/callback"
        element={<GitHubCallbackPage onLoginSuccess={onLoginSuccess} />}
      />

      <Route path="/" element={<Navigate to="/career" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
