import { useState, type ReactNode } from "react";

import styles from "./Collapsible.module.css";

/** Collapsible のプロパティ型 */
type CollapsibleProps = {
  /** ヘッダーに表示するタイトル（テキスト・DirtyDot 等の装飾を含められる） */
  title: ReactNode;
  /** 初期状態で開いているか（既定: 開いた状態） */
  defaultOpen?: boolean;
  /** ヘッダー右側に置く操作（削除ボタン等）。トグルとは別領域でクリックを奪わない。 */
  headerActions?: ReactNode;
  /** 見出しの見た目バリアント（section=セクション見出し相当 / entry=エントリ見出し相当） */
  variant?: "section" | "entry";
  /** 折りたたみ対象の中身 */
  children: ReactNode;
};

/**
 * クリックで開閉できる汎用の折りたたみコンテナ。
 * 資格セクションや会社（職務経歴）単位など、表示量が多い領域を畳めるようにするために使う。
 */
export function Collapsible({
  title,
  defaultOpen = true,
  headerActions,
  variant = "section",
  children,
}: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div>
      <div className={styles.headerRow}>
        <button
          type="button"
          className={`${styles.toggle} ${styles[variant]}`}
          aria-expanded={open}
          onClick={() => setOpen((prev) => !prev)}
        >
          <span className={styles.chevron} data-open={open} aria-hidden="true">
            ▶
          </span>
          <span className={styles.titleText}>{title}</span>
        </button>
        {headerActions ? <div className={styles.actions}>{headerActions}</div> : null}
      </div>
      {open ? <div className={styles.body}>{children}</div> : null}
    </div>
  );
}
