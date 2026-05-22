type Props = {
  /** true のときに 🔴 を描画する。false なら何もレンダリングしない。 */
  visible: boolean;
  /** ホバー時のツールチップ。デフォルトは「未保存の変更があります」。 */
  title?: string;
};

/**
 * 未保存マーク（🔴）。
 * VS Code のファイル変更マーク同様、編集済みだが未保存の項目を示す。
 * 配下に未保存項目があれば親見出しにも同じマークを出すことで小要素 → 大項目への伝播を表現する。
 */
export function DirtyDot({ visible, title = "未保存の変更があります" }: Props) {
  if (!visible) return null;
  return (
    <span
      role="img"
      aria-label={title}
      title={title}
      data-testid="dirty-dot"
      style={{ marginLeft: "0.35rem", fontSize: "0.7em", verticalAlign: "middle" }}
    >
      🔴
    </span>
  );
}
