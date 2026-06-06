import { useMemo, type ReactNode, type Ref } from "react";
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
  /** textarea への ref（バリデーション失敗時のフォーカス用） */
  textareaRef?: Ref<HTMLTextAreaElement>;
  /** バリデーション失敗フィールドとして強調するか（aria-invalid を付与） */
  invalid?: boolean;
  /** 親（モーダル等）の高さいっぱいに伸長するか（既定 false でインライン用途は不変） */
  fill?: boolean;
};

/**
 * Markdownテキストエリア。入力内容をリアルタイムでプレビュー表示する。
 */
export function MarkdownTextarea({
  label,
  value,
  onChange,
  rows = 3,
  placeholder,
  required,
  labelAdornment,
  textareaRef,
  invalid,
  fill = false,
}: Props) {
  const renderedHtml = useMemo(() => renderMarkdown(value), [value]);

  return (
    <div className={`${styles.wrapper} ${fill ? styles.fill : ""}`}>
      <span className={shared.labelText}>
        {label}
        {required && <span className={shared.requiredBadge}>必須</span>}
        {labelAdornment}
      </span>
      <div className={styles.editorRow}>
        <textarea
          ref={textareaRef}
          rows={rows}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required={required}
          aria-invalid={invalid || undefined}
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
