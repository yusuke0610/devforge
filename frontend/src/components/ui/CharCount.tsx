import { charCountLabel } from "../../constants/messages";
import { markdownToPlainText } from "../../utils/markdown";
import { countNonWhitespace } from "../../utils/text";
import styles from "./CharCount.module.css";

type Props = {
  /** 計測対象のテキスト（Markdown 原文） */
  value: string;
};

/**
 * 入力モーダルの右下に表示する文字数カウント。
 * Markdown 記法（`**`・`#`・リンク URL 等）と空白は除外し、描画後の表示テキストの文字数を数える。
 */
export function CharCount({ value }: Props) {
  const count = countNonWhitespace(markdownToPlainText(value));
  return <div className={styles.charCount}>{charCountLabel(count)}</div>;
}
