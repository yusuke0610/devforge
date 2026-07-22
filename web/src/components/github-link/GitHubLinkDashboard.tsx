import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  runGitHubLink,
  getGitHubLinkCache,
  getGitHubLinkCacheStatus,
  getGitHubLinkProgress,
  toAppError,
  type GitHubLinkResponse,
} from "../../api";
import { InlineSpinner } from "../ui/InlineSpinner";
import { AsyncTaskLoading } from "../ui/AsyncTaskLoading";
import { useAppErrorToast } from "../ui/toast";
import {
  FALLBACK_MESSAGES,
  GITHUB_LINK_MESSAGES,
  LOADING_MESSAGES,
  RESUME_DRAFT_MESSAGES,
  UI_MESSAGES,
  yearLabel,
} from "../../constants/messages";
import { useAsyncTaskPage } from "../../hooks/useAsyncTaskPage";
import { useResumeDraftPdf } from "../../hooks/useResumeDraftPdf";
import { PdfPreviewModal } from "../forms/PdfPreviewModal";
import { ContributionHeatmap } from "./ContributionHeatmap";
import { LanguageBar } from "./LanguageBar";
import { SkillDisplaySection } from "./SkillDisplaySection";
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
  // ヒートマップで表示中の年（null のときは最新年=配列先頭を表示）
  const [selectedYear, setSelectedYear] = useState<number | null>(null);

  const { phase, result, error, setError, transitionToPolling } =
    useAsyncTaskPage<GitHubLinkResponse>({
      loadCache: async () => {
        const cache = await getGitHubLinkCache();
        // result は生成型では optional（`GitHubLinkResponse | null | undefined`）のため null に正規化する。
        return { result: cache.result ?? null, status: cache.status };
      },
      checkStatus: getGitHubLinkCacheStatus,
      fetchProgress: getGitHubLinkProgress,
    });

  // 連携実行・ポーリング失敗のエラー（AppErrorState）をトーストで通知する（回復アクション付き・手動クローズ）。
  useAppErrorToast(error);

  // 経歴書ドラフト PDF 生成（ADR-0018）。モデルは Claude Haiku 固定（ADR-0023）
  const draft = useResumeDraftPdf();
  useAppErrorToast(draft.error);

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
        {!result ? (
          <div className={styles.emptyState}>
            <p>{UI_MESSAGES.GITHUB_LINK_EMPTY}</p>
          </div>
        ) : (
          <>
            <div className={styles.dashboardHeader}>
              <h1>{result.username} の連携結果</h1>
            </div>

            {/* アクティビティ（年ごとのコントリビューションヒートマップ） */}
            {(() => {
              const calendars = result.contribution_calendars ?? [];
              if (calendars.length === 0) return null;
              // selectedYear が未選択 or 該当年が無い場合は先頭（最新年）にフォールバック
              const active =
                calendars.find((c) => c.year === selectedYear) ?? calendars[0];
              return (
                <div className={styles.section}>
                  <div className={styles.sectionHeader}>
                    <h2>{GITHUB_LINK_MESSAGES.ACTIVITY_HEADING}</h2>
                    <select
                      className={styles.yearSelect}
                      value={active.year}
                      onChange={(e) => setSelectedYear(Number(e.target.value))}
                      aria-label={GITHUB_LINK_MESSAGES.YEAR_SELECT_ARIA}
                    >
                      {calendars.map((c) => (
                        <option key={c.year} value={c.year}>
                          {yearLabel(c.year)}
                        </option>
                      ))}
                    </select>
                  </div>
                  <ContributionHeatmap calendar={active} />
                </div>
              );
            })()}

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
                  <div className={styles.statLabel}>言語</div>
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

            {/* スキル一覧 + 表示名の human-in-the-loop 確定（ADR-0016 D11） */}
            <SkillDisplaySection />

            {/* 経歴書ドラフト PDF 生成（ADR-0018） */}
            <div className={styles.section}>
              <h2>{RESUME_DRAFT_MESSAGES.HEADING}</h2>
              <p className={styles.summaryText}>{RESUME_DRAFT_MESSAGES.HINT}</p>
              <button
                type="button"
                className={styles.downloadButton}
                onClick={() => void draft.generate()}
                disabled={draft.generating}
              >
                {draft.generating ? (
                  <InlineSpinner label={RESUME_DRAFT_MESSAGES.GENERATING} />
                ) : (
                  RESUME_DRAFT_MESSAGES.GENERATE
                )}
              </button>
              <p className={styles.summaryText}>{RESUME_DRAFT_MESSAGES.NOT_SAVED_NOTE}</p>
            </div>
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
      {draft.previewUrl && (
        <PdfPreviewModal previewUrl={draft.previewUrl} onClose={draft.closePreview} />
      )}
    </>
  );
}
