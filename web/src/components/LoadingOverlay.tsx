import shared from "../styles/shared.module.css";

/**
 * 全画面ローディングオーバーレイ。
 * データ読み込み中にフォーム操作をブロックし、読み込み状態を表示する。
 */
export function LoadingOverlay() {
  return (
    <div className={shared.loadingOverlay}>
      <div className={shared.loadingSpinner} />
      <p className={shared.loadingText}>読み込み中...</p>
    </div>
  );
}
