import { useState } from "react";
import {
  analyzeGitHub,
  getAnalysisCache,
  getAnalysisCacheStatus,
  getAnalysisProgress,
  toAppError,
  type AnalysisResponse,
} from "../../api";
import { ErrorToast } from "../ui/ErrorToast";
import { InlineSpinner } from "../ui/InlineSpinner";
import { AsyncTaskLoading } from "../ui/AsyncTaskLoading";
import { LOADING_MESSAGES } from "../../constants/messages";
import { useAsyncAnalysisPage } from "../../hooks/analysis/useAsyncAnalysisPage";
import { LanguageBar } from "./LanguageBar";
import { TechBar } from "./TechBar";
import shared from "../../styles/shared.module.css";
import styles from "./GitHubAnalysisPage.module.css";

/**
 * GitHub 分析結果を表示するダッシュボードコンポーネント。
 * 初回表示時にDBキャッシュを読み込み、保存済みの結果があればそのまま表示する。
 * 「再分析」ボタン押下時のみパイプラインを再実行する。
 *
 * 職務経歴書ページと同様に、フェーズ（読み込み/入力/ポーリング/結果）に関わらず
 * `shared.pageHeader` のタイトルバーを常時表示する。
 */
export function GitHubAnalysisPage() {
  const [includeForks, setIncludeForks] = useState(false);

  const {
    phase,
    result,
    setResult,
    error,
    setError,
    transitionToPolling,
    backToInput,
  } = useAsyncAnalysisPage<AnalysisResponse>({
    loadCache: async () => {
      const cache = await getAnalysisCache();
      return { result: cache.analysis_result, status: cache.status };
    },
    checkStatus: getAnalysisCacheStatus,
    fetchProgress: getAnalysisProgress,
  });

  /**
   * GitHub 分析を開始します（非同期バックグラウンド）。
   */
  const handleAnalyze = async () => {
    setError(null);
    try {
      await analyzeGitHub({ include_forks: includeForks });
      transitionToPolling();
    } catch (e) {
      setError(toAppError(e, "分析に失敗しました"));
    }
  };

  /**
   * 入力画面に戻ります（再分析用）。
   */
  const handleBack = () => {
    setResult(null);
    backToInput();
  };

  /**
   * フェーズごとの本体を描画する。
   * ヘッダーは常時表示するため、ここでは pageBody に収める中身のみを返す。
   */
  const renderBody = () => {
    // ── フェーズ: キャッシュ読み込み中 ──────────────────────────────
    if (phase === "loading-cache") {
      return <InlineSpinner label="読み込み中..." />;
    }

    // ── フェーズ: 入力 ──────────────────────────────────────────
    if (phase === "input") {
      return (
        <div className={styles.inputCard}>
          <p>あなたのGitHubアクティビティからスキルとキャリアを分析します</p>

          <div className={styles.advancedOptions}>
            <div className={styles.checkbox}>
              <input
                type="checkbox"
                id="includeForks"
                checked={includeForks}
                onChange={(e) => setIncludeForks(e.target.checked)}
              />
              <label htmlFor="includeForks">フォークしたリポジトリを含む</label>
            </div>
          </div>

          <button
            type="button"
            className={styles.analyzeButton}
            onClick={handleAnalyze}
          >
            分析開始
          </button>

          {error && (
            <ErrorToast
              code={error.code}
              message={error.message}
              action={error.action}
              errorId={error.errorId}
              onRetry={handleAnalyze}
            />
          )}
        </div>
      );
    }

    // ── フェーズ: ポーリング中 ────────────────────────────────────────
    if (phase === "polling") {
      return <AsyncTaskLoading label={LOADING_MESSAGES.GITHUB_ANALYSIS} />;
    }

    // ── フェーズ: 分析結果ダッシュボード ───────────────────────────────
    if (!result) return null;

    return (
      <div className={styles.dashboard}>
        {/* ユーザー名見出し（再分析ボタンはページヘッダーへ移設済み） */}
        <div className={styles.dashboardHeader}>
          <h1>{result.username} の分析結果</h1>
        </div>

        {error && (
          <ErrorToast
            code={error.code}
            message={error.message}
            action={error.action}
            errorId={error.errorId}
            onRetry={handleAnalyze}
          />
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
              <TechBar techs={result.detected_frameworks} ariaLabel="検出フレームワーク一覧" />
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
      </div>
    );
  };

  return (
    <>
      <div className={shared.pageHeader}>
        <h1>GitHub分析</h1>
        {phase === "result" && result && (
          <div className={shared.pageHeaderActions}>
            <button type="button" onClick={handleBack}>
              再分析
            </button>
          </div>
        )}
      </div>
      <div className={shared.pageBody}>{renderBody()}</div>
    </>
  );
}
