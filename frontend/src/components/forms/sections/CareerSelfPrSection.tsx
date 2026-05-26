import shared from "../../../styles/shared.module.css";
import { DirtyDot } from "../../ui/DirtyDot";
import { Skeleton } from "../../ui/Skeleton";
import { MarkdownTextarea } from "../MarkdownTextarea";

/** CareerSelfPrSection のプロパティ型 */
type Props = {
  /** 自己PR（Markdown） */
  selfPr: string;
  /** ローディング中（Skeleton 表示） */
  loading: boolean;
  /** 値変更ハンドラ */
  onChange: (value: string) => void;
  /** 未保存変更があるか */
  dirty?: boolean;
};

/**
 * 職務経歴書の「自己PR」セクション。
 * 元 CareerResumeForm の JSX をセクション単位で読みやすくするための切り出し。
 */
export function CareerSelfPrSection({ selfPr, loading, onChange, dirty = false }: Props) {
  return (
    <section className={shared.section}>
      {loading ? (
        <Skeleton height="110px" />
      ) : (
        <MarkdownTextarea
          label="自己PR"
          value={selfPr}
          onChange={onChange}
          rows={4}
          required
          labelAdornment={<DirtyDot visible={dirty} />}
        />
      )}
    </section>
  );
}
