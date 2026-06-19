import { LOADING_MESSAGES } from "../../constants/messages";
import styles from "./AsyncTaskLoading.module.css";

type Props = {
  /** スピナー下に表示する処理内容のラベル（機能ごとに変える） */
  label: string;
};

/**
 * 非同期バックグラウンドタスク共通のローディング UI。
 * PDF アップロード / GitHub 連携 / ブログ分析 / キャリア分析 で統一して使う。
 *
 * スピナー + 処理内容ラベル + 共通の補足メッセージ2行
 * （「他の画面に移動しても処理は継続されます」「この処理には時間がかかります」）で構成する。
 */
export function AsyncTaskLoading({ label }: Props) {
  return (
    <div className={styles.wrapper}>
      <div className={styles.spinner} />
      <p className={styles.label}>{label}</p>
      <div className={styles.hints}>
        <p className={styles.hint}>{LOADING_MESSAGES.BACKGROUND_CONTINUES}</p>
        <p className={styles.hint}>{LOADING_MESSAGES.TAKES_TIME}</p>
      </div>
    </div>
  );
}
