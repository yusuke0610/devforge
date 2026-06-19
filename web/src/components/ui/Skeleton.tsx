import styles from "./Skeleton.module.css";

type Props = {
  height?: number | string;
  width?: number | string;
  borderRadius?: number | string;
};

/** シマーアニメーション付きスケルトンプレースホルダー。 */
export function Skeleton({ height = "1rem", width = "100%", borderRadius }: Props) {
  return (
    <span
      className={styles.skeleton}
      style={{
        height,
        width,
        borderRadius: borderRadius ?? undefined,
      }}
    />
  );
}
