import styles from "./InlineSpinner.module.css";

type Size = "sm" | "md" | "lg";

type Props = {
  /** スピナー下に表示するラベルテキスト */
  label?: string;
  /** ラベルの下に表示する補足テキスト */
  sublabel?: string;
  /** スピナーのサイズ（デフォルト: md） */
  size?: Size;
};

/** インラインスピナー。ページ内のローディング状態を表示する共通コンポーネント。 */
export function InlineSpinner({ label, sublabel, size = "md" }: Props) {
  return (
    <div className={styles.wrapper}>
      <div className={`${styles.spinner} ${styles[size]}`} />
      {label && <p className={styles.label}>{label}</p>}
      {sublabel && <p className={styles.sublabel}>{sublabel}</p>}
    </div>
  );
}
