import { useMemo, type ReactNode } from "react";
import { renderMarkdown } from "../../utils/markdown";
import shared from "../../styles/shared.module.css";
import styles from "./MarkdownTextarea.module.css";

type Props = {
  /** フィールドのラベル */
  label: string;
  /** テキストの値 */
  value: string;
  /** 値変更コールバック */
  onChange: (value: string) => void;
  /** textarea の行数（デフォルト: 3） */
  rows?: number;
  /** placeholder */
  placeholder?: string;
  /** 必須フィールドかどうか */
  required?: boolean;
  /** ラベル横に追加する装飾要素（例: 未保存マーク 🔴） */
  labelAdornment?: ReactNode;
};

/**
 * Markdownテキストエリア。入力内容をリアルタイムでプレビュー表示する。
 */
export function MarkdownTextarea({ label, value, onChange, rows = 3, placeholder, required, labelAdornment }: Props) {
  const renderedHtml = useMemo(() => renderMarkdown(value), [value]);

  return (
    <div className={styles.wrapper}>
      <span className={shared.labelText}>
        {label}
        {required && <span className={shared.requiredBadge}>必須</span>}
        {labelAdornment}
      </span>
      <div className={styles.editorRow}>
        <textarea
          rows={rows}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required={required}
          className={styles.editor}
        />
        {value && (
          <div
            className={styles.preview}
            style={{ minHeight: `${rows * 1.5}rem` }}
            dangerouslySetInnerHTML={{ __html: renderedHtml }}
          />
        )}
      </div>
    </div>
  );
}
