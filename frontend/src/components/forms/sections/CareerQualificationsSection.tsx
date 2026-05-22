import type { Dispatch, SetStateAction } from "react";
import { blankResumeQualification } from "../../../constants";
import type { QualificationDirty } from "../../../hooks/career/useCareerDirty";
import type { CareerFormState } from "../../../payloadBuilders";
import type { ResumeQualification } from "../../../types";
import shared from "../../../styles/shared.module.css";
import { DirtyDot } from "../../ui/DirtyDot";
import { Skeleton } from "../../ui/Skeleton";
import { Combobox } from "../Combobox";

/** CareerQualificationsSection のプロパティ型 */
type Props = {
  /** 資格データ配列 */
  qualifications: ResumeQualification[];
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
};

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
}: Props) {
  /** 資格フィールド変更ハンドラ */
  const updateField = (index: number, key: keyof ResumeQualification, value: string) => {
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
      <h2>
        資格
        <DirtyDot visible={sectionDirty} />
      </h2>
      {loading ? (
        <div className={shared.entry}>
          <Skeleton height="56px" />
        </div>
      ) : (
        <>
          {qualifications.map((qualification, index) => {
            const rowDirty = qualificationsDirty?.[index];
            return (
              <div key={`qualification-${index}`} className={shared.entry}>
                <div className={shared.inline}>
                  <label>
                    資格名 ※プルダウンにないものはテキストで入力できます。
                    <DirtyDot visible={Boolean(rowDirty?.fields.name)} />
                    <Combobox
                      value={qualification.name}
                      onChange={(val) => updateField(index, "name", val)}
                      options={qualificationNames}
                      placeholder="例: 基本情報技術者試験"
                      allowCustom
                    />
                  </label>
                  <label>
                    取得日
                    <DirtyDot visible={Boolean(rowDirty?.fields.acquired_date)} />
                    <input
                      type="date"
                      value={qualification.acquired_date}
                      onChange={(e) => updateField(index, "acquired_date", e.target.value)}
                    />
                  </label>
                </div>
                <button type="button" className="danger" onClick={() => removeRow(index)}>
                  資格を削除
                </button>
              </div>
            );
          })}
          <button type="button" className="ghost" onClick={addRow}>
            資格を追加
          </button>
        </>
      )}
    </section>
  );
}
