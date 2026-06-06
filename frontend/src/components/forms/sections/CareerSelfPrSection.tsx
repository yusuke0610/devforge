import type { CareerFieldLocator } from "../../../payloadBuilders";
import { UI_MESSAGES } from "../../../constants/messages";
import shared from "../../../styles/shared.module.css";
import { MarkdownFieldTrigger } from "../MarkdownFieldTrigger";

/** CareerSelfPrSection のプロパティ型 */
type Props = {
  /** 自己PR（Markdown） */
  selfPr: string;
  /** ローディング中（Skeleton 表示） */
  loading: boolean;
  /** 自己PR の入力モーダルを開く */
  onEdit: () => void;
  /** 未保存変更があるか */
  dirty?: boolean;
  /** バリデーション失敗フィールドの位置情報（フォーカス・赤枠用） */
  focusLocator?: CareerFieldLocator | null;
};

/**
 * 職務経歴書の「自己PR」セクション。
 * 入力欄がノイズになるため専用モーダルに逃がし、ここではプレビュー + 編集ボタンを置く。
 */
export function CareerSelfPrSection({
  selfPr,
  loading,
  onEdit,
  dirty = false,
  focusLocator = null,
}: Props) {
  const invalid = focusLocator?.kind === "self_pr";

  return (
    <section className={shared.section}>
      <MarkdownFieldTrigger
        label={UI_MESSAGES.FIELD_SELF_PR}
        value={selfPr}
        loading={loading}
        dirty={dirty}
        invalid={invalid}
        onEdit={onEdit}
      />
    </section>
  );
}
