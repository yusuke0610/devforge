import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import {
  runGitHubLink,
  getGitHubLinkCache,
  getGitHubLinkCacheStatus,
  getGitHubLinkProgress,
  toAppError,
  type GitHubLinkResponse,
} from "../../api";
import { ErrorToast } from "../ui/ErrorToast";
import { InlineSpinner } from "../ui/InlineSpinner";
import { AsyncTaskLoading } from "../ui/AsyncTaskLoading";
import { FALLBACK_MESSAGES, LOADING_MESSAGES, UI_MESSAGES } from "../../constants/messages";
import { useAsyncTaskPage } from "../../hooks/useAsyncTaskPage";
import { ContributionHeatmap } from "./ContributionHeatmap";
import { LanguageBar } from "./LanguageBar";
import { TechBar } from "./TechBar";
import shared from "../../styles/shared.module.css";
import styles from "./GitHubLinkDashboard.module.css";

/** サイドバーから渡される連携実行の意図 */
type GitHubLinkNavState = {
  runNonce?: number;
  includeForks?: boolean;
} | null;

/**
 * GitHub 連携結果を表示するダッシュボードコンポーネント（表示専用）。
 * 初回表示時にDBキャッシュを読み込み、保存済みの結果があればそのまま表示する。
 *
 * 連携 API のトリガーはサイドバーの「GitHub連携」クリックのみ。
 * サイドバーは navigate state に runNonce を載せて遷移し、本コンポーネントが
 * それを検知して連携を実行（ポーリング）・エラー表示を担う。
 */
export function GitHubLinkDashboard() {
  const location = useLocation();
  const handledNonceRef = useRef<number | undefined>(undefined);

  const { phase, result, error, setError, transitionToPolling } =
    useAsyncTaskPage<GitHubLinkResponse>({
      loadCache: async () => {
        const cache = await getGitHubLinkCache();
        return { result: cache.result, status: cache.status };
      },
      checkStatus: getGitHubLinkCacheStatus,
      fetchProgress: getGitHubLinkProgress,
    });

  /**
   * GitHub 連携を実行する（非同期バックグラウンド）。
   * サイドバーから渡された includeForks を使う。
   */
  const runLink = async (includeForks: boolean) => {
    setError(null);
    try {
      await runGitHubLink({ include_forks: includeForks });
      transitionToPolling();
    } catch (e) {
      setError(toAppError(e, FALLBACK_MESSAGES.GITHUB_LINK));
    }
  };

  // サイドバーからの実行意図（runNonce）を検知して連携を実行する。
  useEffect(() => {
    const state = location.state as GitHubLinkNavState;
    if (state?.runNonce && state.runNonce !== handledNonceRef.current) {
      handledNonceRef.current = state.runNonce;
      void runLink(state.includeForks ?? false);
    }
    // location.state（サイドバークリック）変化時のみトリガーする
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);

  /**
   * フェーズごとの本体を描画する。
   * ヘッダーは常時表示するため、ここでは pageBody に収める中身のみを返す。
   */
  const renderBody = () => {
    if (phase === "loading-cache") {
      return <InlineSpinner label="読み込み中..." />;
    }

    if (phase === "polling") {
      return <AsyncTaskLoading label={LOADING_MESSAGES.GITHUB_LINK} />;
    }

    // ── 入力 / 結果フェーズ ─────────────────────────────────────────
    return (
      <div className={styles.dashboard}>
        {error && (
          <ErrorToast
            code={error.code}
            message={error.message}
            action={error.action}
            errorId={error.errorId}
          />
        )}

        {!result ? (
          <div className={styles.emptyState}>
            <p>{UI_MESSAGES.GITHUB_LINK_EMPTY}</p>
          </div>
        ) : (
          <>
            <div className={styles.dashboardHeader}>
              <h1>{result.username} の連携結果</h1>
            </div>

            {/* アクティビティ（コントリビューションヒートマップ） */}
            {result.contribution_calendar && (
              <div className={styles.section}>
                <h2>Activity</h2>
                <ContributionHeatmap calendar={result.contribution_calendar} />
              </div>
            )}

            {/* 概要 */}
            <div className={styles.section}>
              <h2>Overview</h2>
              <div className={styles.overviewCards}>
                <div className={styles.statCard}>
                  <div className={styles.statValue}>{result.repos_analyzed}</div>
                  <div className={styles.statLabel}>リポジトリ</div>
                </div>
                <div className={styles.statCard}>
                  <div className={styles.statValue}>{result.unique_skills}</div>
                  <div className={styles.statLabel}>スキル</div>
                </div>
              </div>
            </div>

            {/* 構成 */}
            {result.languages && Object.keys(result.languages).length > 0 && (
              <div className={styles.section}>
                <h2>Languages</h2>
                <LanguageBar languages={result.languages} />
              </div>
            )}

            {/* 検出フレームワーク */}
            {result.detected_frameworks &&
              Object.keys(result.detected_frameworks).length > 0 && (
                <div className={styles.section}>
                  <h2>Frameworks</h2>
                  <TechBar
                    techs={result.detected_frameworks}
                    ariaLabel="検出フレームワーク一覧"
                  />
                </div>
              )}

            {/* DevTools */}
            {result.detected_devtools &&
              Object.keys(result.detected_devtools).length > 0 && (
                <div className={styles.section}>
                  <h2>DevTools</h2>
                  <TechBar techs={result.detected_devtools} />
                </div>
              )}

            {/* インフラ */}
            {result.detected_infras &&
              Object.keys(result.detected_infras).length > 0 && (
                <div className={styles.section}>
                  <h2>Infra</h2>
                  <TechBar techs={result.detected_infras} />
                </div>
              )}
          </>
        )}
      </div>
    );
  };

  return (
    <>
      <div className={shared.pageHeader}>
        <h1>GitHub連携</h1>
      </div>
      <div className={shared.pageBody}>{renderBody()}</div>
    </>
  );
}
