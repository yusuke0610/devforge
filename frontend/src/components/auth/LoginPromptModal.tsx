import { useState } from "react";

import { initiateGitHubLogin } from "../../api";
import { AUTH_PROMPT_MESSAGES } from "../../constants/messages";
import { GitHubMarkIcon } from "../icons/GitHubMarkIcon";
import styles from "./LoginPromptModal.module.css";

/**
 * 未ログインで職務経歴書を保存しようとしたときに表示するログイン促進モーダル。
 *
 * 入力済みドラフトは呼び出し側で sessionStorage に退避済み。ここではログインへ誘導するだけで、
 * GitHub OAuth へリダイレクトする。往復後 `/career` に戻ると useCareerDraftRestore がドラフトを復元する。
 */
export function LoginPromptModal({ onClose }: { onClose: () => void }) {
  const [isLoading, setIsLoading] = useState(false);

  const handleGitHubLogin = async () => {
    setIsLoading(true);
    try {
      await initiateGitHubLogin(window.location.origin);
    } catch {
      // 開始に失敗したらボタンを再操作可能に戻す（エラーはリダイレクト前のため握って良い）。
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-label={AUTH_PROMPT_MESSAGES.TITLE}
        onClick={(e) => e.stopPropagation()}
      >
        {isLoading ? (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <p>{AUTH_PROMPT_MESSAGES.REDIRECTING}</p>
          </div>
        ) : (
          <>
            <h2 className={styles.title}>{AUTH_PROMPT_MESSAGES.TITLE}</h2>
            <p className={styles.description}>{AUTH_PROMPT_MESSAGES.DESCRIPTION}</p>
            <p className={styles.draftKept}>{AUTH_PROMPT_MESSAGES.DRAFT_KEPT}</p>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.githubLogin}
                onClick={() => {
                  void handleGitHubLogin();
                }}
              >
                <GitHubMarkIcon className={styles.githubIcon} />
                {AUTH_PROMPT_MESSAGES.GITHUB_LOGIN}
              </button>
              <button type="button" className={styles.later} onClick={onClose}>
                {AUTH_PROMPT_MESSAGES.LATER}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
