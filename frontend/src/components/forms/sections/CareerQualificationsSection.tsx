import type { Dispatch, SetStateAction } from "react";
import { blankResumeQualification } from "../../../constants";
import type { QualificationDirty } from "../../../hooks/career/useCareerDirty";
import type { CareerFieldLocator, CareerFormState } from "../../../payloadBuilders";
import type { ResumeQualificationItem } from "../../../api/types";
import { UI_MESSAGES } from "../../../constants/messages";
import { useFocusOnMatch } from "../../../hooks/useFocusOnMatch";
import shared from "../../../styles/shared.module.css";
import styles from "../CareerResumeForm.module.css";
import { Collapsible } from "../../ui/Collapsible";
import { DeleteIconButton } from "../../ui/DeleteIconButton";
import { DirtyDot } from "../../ui/DirtyDot";
import { Skeleton } from "../../ui/Skeleton";
import { PlusIcon } from "../../icons/PlusIcon";
import { Combobox } from "../Combobox";

/** CareerQualificationsSection のプロパティ型 */
type Props = {
  /** 資格データ配列 */
  qualifications: ResumeQualificationItem[];
  /** マスタから取得した資格名候補 */
  qualificationNames: string[];
  /** ローディング中（Skeleton 表示） */
  loading: boolean;
  /** フォーム状態更新ディスパッチャ */
  setForm: Dispatch<SetStateAction<CareerFormState>>;
  /** 各資格行の未保存情報。要素数は qualifications と一致する想定。 */
  qualificationsDirty?: QualificationDirty[];
  /** 「資格」セクション全体の未保存集約フラグ。 */
  sectionDirty?: boolean;
  /** バリデーション失敗フィールドの位置情報（フォーカス・赤枠・折りたたみ展開用） */
  focusLocator?: CareerFieldLocator | null;
  /** フォーカス発火の nonce（折りたたみ自動展開の再発火鍵） */
  focusNonce?: number;
};

/** 資格 1 行分の入力。可変長のため別コンポーネントにして focus hook を使う。 */
type QualificationRowProps = {
  qualification: ResumeQualificationItem;
  index: number;
  qualificationNames: string[];
  rowDirty?: QualificationDirty;
  focusLocator: CareerFieldLocator | null;
  onUpdate: (index: number, key: keyof ResumeQualificationItem, value: string) => void;
  onRemove: (index: number) => void;
};

function QualificationRow({
  qualification,
  index,
  qualificationNames,
  rowDirty,
  focusLocator,
  onUpdate,
  onRemove,
}: QualificationRowProps) {
  const nameInvalid =
    focusLocator?.kind === "qualification" &&
    focusLocator.index === index &&
    focusLocator.field === "name";
  const acquiredInvalid =
    focusLocator?.kind === "qualification" &&
    focusLocator.index === index &&
    focusLocator.field === "acquired_date";
  const nameRef = useFocusOnMatch<HTMLInputElement>(nameInvalid);
  const acquiredRef = useFocusOnMatch<HTMLInputElement>(acquiredInvalid);

  return (
    <div className={shared.entry}>
      <div className={styles.qualificationRow}>
        {/* 資格名:取得日 = 7:3 の幅比で配置 */}
        <div className={shared.inline} style={{ gridTemplateColumns: "7fr 3fr" }}>
          <label>
            <span className={shared.labelText}>
              資格名
              <span className={shared.requiredBadge}>必須</span>
              ※プルダウンにないものはテキストで入力できます。
              <DirtyDot visible={Boolean(rowDirty?.fields.name)} />
            </span>
            <Combobox
              value={qualification.name}
              onChange={(val) => onUpdate(index, "name", val)}
              options={qualificationNames}
              placeholder="例: 基本情報技術者試験"
              allowCustom
              inputRef={nameRef}
              invalid={nameInvalid}
            />
          </label>
          <label>
            <span className={shared.labelText}>
              取得日
              <span className={shared.requiredBadge}>必須</span>
              <DirtyDot visible={Boolean(rowDirty?.fields.acquired_date)} />
            </span>
            <input
              ref={acquiredRef}
              type="month"
              value={qualification.acquired_date}
              onChange={(e) => onUpdate(index, "acquired_date", e.target.value)}
              aria-invalid={acquiredInvalid || undefined}
            />
          </label>
        </div>
        <DeleteIconButton
          label={UI_MESSAGES.RESUME_DELETE_QUALIFICATION}
          onClick={() => onRemove(index)}
        />
      </div>
    </div>
  );
}

/**
 * 職務経歴書の「資格」セクション。資格の追加・削除・編集ハンドラを内包する。
 * 元 CareerResumeForm の JSX をセクション単位で読みやすくするための切り出し。
 */
export function CareerQualificationsSection({
  qualifications,
  qualificationNames,
  loading,
  setForm,
  qualificationsDirty,
  sectionDirty = false,
  focusLocator = null,
  focusNonce = 0,
}: Props) {
  // 資格欄を対象とするエラーなら折りたたみを自動展開する。
  const forceOpenKey = focusLocator?.kind === "qualification" ? focusNonce : null;
  /** 資格フィールド変更ハンドラ */
  const updateField = (index: number, key: keyof ResumeQualificationItem, value: string) => {
    setForm((prev) => ({
      ...prev,
      qualifications: prev.qualifications.map((qualification, i) =>
        i === index ? { ...qualification, [key]: value } : qualification,
      ),
    }));
  };

  /** 資格追加ハンドラ */
  const addRow = () => {
    setForm((prev) => ({
      ...prev,
      qualifications: [...prev.qualifications, { ...blankResumeQualification }],
    }));
  };

  /** 資格削除ハンドラ（最後の 1 件は blank に戻すことで「項目ゼロ」を避ける） */
  const removeRow = (index: number) => {
    setForm((prev) => ({
      ...prev,
      qualifications:
        prev.qualifications.length === 1
          ? [{ ...blankResumeQualification }]
          : prev.qualifications.filter((_, i) => i !== index),
    }));
  };

  return (
    <section className={shared.section}>
      <Collapsible
        variant="section"
        forceOpenKey={forceOpenKey}
        title={
          <>
            資格
            <DirtyDot visible={sectionDirty} />
          </>
        }
      >
        {loading ? (
          <div className={shared.entry}>
            <Skeleton height="56px" />
          </div>
        ) : (
          <>
            {qualifications.map((qualification, index) => (
              <QualificationRow
                key={`qualification-${index}`}
                qualification={qualification}
                index={index}
                qualificationNames={qualificationNames}
                rowDirty={qualificationsDirty?.[index]}
                focusLocator={focusLocator}
                onUpdate={updateField}
                onRemove={removeRow}
              />
            ))}
            <button type="button" className={`ghost ${styles.addButton}`} onClick={addRow}>
              <PlusIcon />
              資格を追加
            </button>
          </>
        )}
      </Collapsible>
    </section>
  );
}
