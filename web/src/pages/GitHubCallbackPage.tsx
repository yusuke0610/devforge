import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { GITHUB_OAUTH_STATE_STORAGE_KEY, handleGitHubCallback } from "../api/auth";
import shared from "../styles/shared.module.css";

type Props = {
  onLoginSuccess: (user: { username: string; is_github_user: boolean }) => void;
};

export default function GitHubCallbackPage({ onLoginSuccess }: Props) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const calledRef = useRef(false);

  useEffect(() => {
    if (calledRef.current) return;
    calledRef.current = true;

    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const storedState = sessionStorage.getItem(GITHUB_OAUTH_STATE_STORAGE_KEY);

    if (!code || !state) {
      navigate("/login?github_error=invalid_callback", { replace: true });
      return;
    }

    // CSRF 検証: sessionStorage の state と URL の state を照合する
    if (!storedState || storedState !== state) {
      sessionStorage.removeItem(GITHUB_OAUTH_STATE_STORAGE_KEY);
      navigate("/login?github_error=state_mismatch", { replace: true });
      return;
    }

    // 使用済み state を削除（リプレイ攻撃防止）
    sessionStorage.removeItem(GITHUB_OAUTH_STATE_STORAGE_KEY);

    handleGitHubCallback(code, state)
      .then((user) => {
        onLoginSuccess(user);
        navigate("/career", { replace: true });
      })
      .catch(() => {
        navigate("/login?github_error=authentication_failed", { replace: true });
      });
  }, [searchParams, navigate, onLoginSuccess]);

  return (
    <div className={shared.loadingOverlay}>
      <div className={shared.loadingSpinner} />
      <p className={shared.loadingText}>GitHubログイン処理中...</p>
    </div>
  );
}
