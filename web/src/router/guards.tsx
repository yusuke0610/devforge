import { Navigate, Outlet } from "react-router-dom";

import { LoadingOverlay } from "../components/LoadingOverlay";

export type AuthUser = { username: string; isGitHubUser: boolean };

type GuardProps = {
  user: AuthUser | null;
  authLoading: boolean;
};

/**
 * 認証済みユーザー専用のルートガード。
 * 未認証時は /login にリダイレクトする。
 */
export function PrivateRoute({ user, authLoading }: GuardProps) {
  if (authLoading) return <LoadingOverlay />;
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

/**
 * 未認証ユーザー専用のルートガード。
 * 認証済み時は /career にリダイレクトする。
 */
export function PublicRoute({ user, authLoading }: GuardProps) {
  if (authLoading) return <LoadingOverlay />;
  if (user) return <Navigate to="/career" replace />;
  return <Outlet />;
}
