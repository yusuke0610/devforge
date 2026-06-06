import { charCountLabel } from "../../constants/messages";
import { countNonWhitespace } from "../../utils/text";
import styles from "./CharCount.module.css";

type Props = {
  /** 計測対象のテキスト */
  value: string;
};

/** 入力モーダルの右下に表示する文字数カウント（空白を含めない）。 */
export function CharCount({ value }: Props) {
  return <div className={styles.charCount}>{charCountLabel(countNonWhitespace(value))}</div>;
}
