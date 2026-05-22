import { FALLBACK_MESSAGES } from "../constants/messages";
import { API_BASE_URL, request } from "./client";
import { PATHS } from "./paths";

type AuthResponse = { username: string; is_github_user: boolean };

export async function getCurrentUser(): Promise<AuthResponse | null> {
  const response = await fetch(`${API_BASE_URL}${PATHS.auth.me}`, {
    credentials: "include",
  });
  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(FALLBACK_MESSAGES.AUTH_CHECK);
  }
  return (await response.json()) as AuthResponse;
}

export async function handleGitHubCallback(code: string, state: string): Promise<AuthResponse> {
  return request<AuthResponse>(PATHS.auth.githubCallback, {
    method: "POST",
    body: JSON.stringify({ code, state }),
  });
}

/** sessionStorage の key。CSRF 検証用に GitHub OAuth state を保持する。 */
export const GITHUB_OAUTH_STATE_STORAGE_KEY = "github_oauth_state";

/** Cloudflare Pages は /auth/** を Cloud Run にプロキシするため、GitHub の
 *  リダイレクト先は SPA ルートの /github/callback に揃え、React で受け取る。
 *  state は sessionStorage で管理し、コールバック時に CSRF 検証する。 */
export async function initiateGitHubLogin(returnTo: string): Promise<void> {
  const params = new URLSearchParams({ return_to: returnTo });
  const response = await fetch(`${API_BASE_URL}${PATHS.auth.githubLoginUrl}?${params.toString()}`, {
    credentials: "include",
  });
  if (!response.ok) throw new Error(FALLBACK_MESSAGES.GITHUB_OAUTH_START);
  const data = (await response.json()) as { authorization_url: string; state: string };
  // CSRF 検証用に state を sessionStorage へ保存する（コールバックで照合）
  sessionStorage.setItem(GITHUB_OAUTH_STATE_STORAGE_KEY, data.state);
  window.location.assign(data.authorization_url);
}

/** サーバー側で refresh_jti を無効化し Cookie を削除する。
 *  401 ハンドラのループを避けるため request ラッパーではなく fetch を直接使う。 */
export async function logout(): Promise<void> {
  await fetch(`${API_BASE_URL}${PATHS.auth.logout}`, {
    method: "POST",
    credentials: "include",
  });
}
