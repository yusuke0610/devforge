import type { CareerFieldLocator } from "../../../payloadBuilders";
import { useFocusOnMatch } from "../../../hooks/useFocusOnMatch";
import shared from "../../../styles/shared.module.css";
import { DirtyDot } from "../../ui/DirtyDot";
import { Skeleton } from "../../ui/Skeleton";
import { MarkdownFieldTrigger } from "../MarkdownFieldTrigger";

/** CareerBasicInfoSection のプロパティ型 */
type Props = {
  /** 氏名 */
  fullName: string;
  /** 職務要約（Markdown） */
  careerSummary: string;
  /** ローディング中（Skeleton 表示） */
  loading: boolean;
  /** フィールド変更ハンドラ */
  onChange: (key: "full_name" | "career_summary", value: string) => void;
  /** 職務要約の入力モーダルを開く */
  onEditCareerSummary: () => void;
  /** 氏名フィールドが未保存か */
  fullNameDirty?: boolean;
  /** 職務要約フィールドが未保存か */
  careerSummaryDirty?: boolean;
  /** バリデーション失敗フィールドの位置情報（フォーカス・赤枠用） */
  focusLocator?: CareerFieldLocator | null;
};

/**
 * 職務経歴書の「基本情報」セクション。氏名と職務要約を表示する。
 * 職務要約は入力欄がノイズになるため専用モーダルに逃がし、ここではプレビュー + 編集ボタンを置く。
 * CareerResumeForm の JSX をセクション単位で読みやすくするための切り出し。
 */
export function CareerBasicInfoSection({
  fullName,
  careerSummary,
  loading,
  onChange,
  onEditCareerSummary,
  fullNameDirty = false,
  careerSummaryDirty = false,
  focusLocator = null,
}: Props) {
  const fullNameInvalid = focusLocator?.kind === "full_name";
  const careerSummaryInvalid = focusLocator?.kind === "career_summary";
  const fullNameRef = useFocusOnMatch<HTMLInputElement>(fullNameInvalid);

  return (
    <section className={shared.section}>
      <label>
        <span className={shared.labelText}>
          氏名<span className={shared.requiredBadge}>必須</span>
          <DirtyDot visible={fullNameDirty} />
        </span>
        {loading ? (
          <Skeleton height="38px" />
        ) : (
          <input
            ref={fullNameRef}
            type="text"
            value={fullName}
            onChange={(e) => onChange("full_name", e.target.value)}
            placeholder="例: 山田 太郎"
            required
            aria-invalid={fullNameInvalid || undefined}
          />
        )}
      </label>
      <MarkdownFieldTrigger
        label="職務要約"
        value={careerSummary}
        loading={loading}
        dirty={careerSummaryDirty}
        invalid={careerSummaryInvalid}
        onEdit={onEditCareerSummary}
      />
    </section>
  );
}
