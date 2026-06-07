import { UI_MESSAGES } from "../../constants/messages";
import shared from "../../styles/shared.module.css";
import { markdownToPlainText } from "../../utils/markdown";
import { DirtyDot } from "../ui/DirtyDot";
import { Skeleton } from "../ui/Skeleton";
import styles from "./MarkdownFieldTrigger.module.css";

/** プレビューに出す最大文字数（超過分は省略記号で切り詰め） */
const PREVIEW_MAX_LENGTH = 10;

/** Markdown 記法を除去し、改行を空白に潰した先頭 10 文字プレビュー文字列を作る。 */
function toPreview(value: string): string {
  const flat = markdownToPlainText(value).replace(/\s+/g, " ").trim();
  if (flat.length <= PREVIEW_MAX_LENGTH) return flat;
  return `${flat.slice(0, PREVIEW_MAX_LENGTH)}…`;
}

type Props = {
  /** フィールド名（自己PR / 職務要約） */
  label: string;
  /** 現在値（Markdown 原文） */
  value: string;
  /** 未保存マーク（セクション/フォームの dirty）を表示するか */
  dirty?: boolean;
  /** バリデーション失敗フィールドとして赤枠で強調するか */
  invalid?: boolean;
  /** ローディング中（Skeleton 表示） */
  loading?: boolean;
  /** 編集ボタン押下で入力モーダルを開くコールバック */
  onEdit: () => void;
};

/**
 * 自己PR・職務要約をフォーム内ではプレビュー + 編集ボタンで表示するトリガ。
 * 大きな入力欄を専用モーダルへ逃がし、フォーム本体のノイズを減らす。
 */
export function MarkdownFieldTrigger({
  label,
  value,
  dirty = false,
  invalid = false,
  loading = false,
  onEdit,
}: Props) {
  const preview = toPreview(value);
  const isEmpty = preview.length === 0;

  return (
    <div className={styles.wrapper}>
      <div className={styles.head}>
        <span className={shared.labelText}>
          {label}
          <span className={shared.requiredBadge}>必須</span>
          <DirtyDot visible={dirty} />
        </span>
      </div>
      {loading ? (
        <Skeleton height="44px" />
      ) : (
        <button
          type="button"
          className={`${styles.trigger} ${invalid ? styles.invalid : ""}`}
          onClick={onEdit}
          aria-label={`${label}を${UI_MESSAGES.EDIT}`}
          aria-invalid={invalid || undefined}
        >
          <span className={`${styles.preview} ${isEmpty ? styles.empty : ""}`}>
            {isEmpty ? UI_MESSAGES.FIELD_NOT_ENTERED : preview}
          </span>
          <span className={styles.editLabel}>{UI_MESSAGES.EDIT}</span>
        </button>
      )}
    </div>
  );
}
