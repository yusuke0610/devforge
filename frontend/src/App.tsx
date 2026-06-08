import ErrorBoundary from "./components/ErrorBoundary";
import { LoginPromptProvider } from "./components/auth/LoginPromptProvider";
import { useAuthSession } from "./hooks/useAuthSession";
import { useTheme } from "./hooks/useTheme";
import { AppRoutes } from "./router";

/**
 * アプリケーションのメインエントリーポイントコンポーネント。
 * 認証ライフサイクルとテーマは個別フックに委譲し、本コンポーネントは wiring に専念する。
 */
export default function App() {
  const { theme, toggleTheme } = useTheme();
  const { user, authLoading, githubError, handleLogout, handleLoginSuccess } =
    useAuthSession();

  return (
    <ErrorBoundary>
      <LoginPromptProvider>
        <AppRoutes
          user={user}
          authLoading={authLoading}
          theme={theme}
          onToggleTheme={toggleTheme}
          githubError={githubError}
          onLogout={() => {
            void handleLogout();
          }}
          onLoginSuccess={handleLoginSuccess}
        />
      </LoginPromptProvider>
    </ErrorBoundary>
  );
}
