import { useNavigate } from "react-router-dom";

import styles from "./NotFoundPage.module.css";

export default function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className={styles.root}>
      <div className={styles.card}>
        <p className={styles.code}>404</p>
        <h1 className={styles.title}>ページが見つかりません</h1>
        <p className={styles.description}>
          お探しのページは存在しないか、移動した可能性があります。
        </p>
        <button type="button" className={styles.button} onClick={() => navigate("/career")}>
          ホームに戻る
        </button>
      </div>
    </div>
  );
}
