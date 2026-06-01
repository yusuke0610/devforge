import { CAPITAL_UNITS } from "../../../constants";
import type { CareerClientFieldKey, CareerExperienceFieldKey } from "../../../formTypes";
import type { ExperienceDirty } from "../../../hooks/career/useCareerDirty";
import {
  validateDateRange,
  type CareerExperienceForm,
  type CareerProjectForm,
} from "../../../payloadBuilders";
import shared from "../../../styles/shared.module.css";
import styles from "../CareerResumeForm.module.css";
import { Collapsible } from "../../ui/Collapsible";
import { DirtyDot } from "../../ui/DirtyDot";
import { ClientEditor } from "./ClientEditor";

/** CareerExperienceEditor のプロパティ型 */
type CareerExperienceEditorProps = {
  /** 編集対象の職務経歴データ */
  exp: CareerExperienceForm;
  /** この職務経歴のインデックス */
  expIndex: number;
  /** フィールド変更ハンドラ */
  onUpdateExperienceField: (
    index: number,
    key: CareerExperienceFieldKey,
    value: string | boolean,
  ) => void;
  /** 取引先フィールド変更ハンドラ */
  onUpdateClientField: (
    expIndex: number,
    clientIndex: number,
    key: CareerClientFieldKey,
    value: string,
  ) => void;
  /** 取引先「取引先なし」切替ハンドラ */
  onUpdateClientHasClient: (expIndex: number, clientIndex: number, value: boolean) => void;
  /** 取引先「休暇」切替ハンドラ */
  onUpdateClientIsVacation: (expIndex: number, clientIndex: number, value: boolean) => void;
  /** 休暇「継続中」切替ハンドラ */
  onUpdateClientVacationIsCurrent: (expIndex: number, clientIndex: number, value: boolean) => void;
  /** 取引先追加ハンドラ */
  onAddClient: (expIndex: number) => void;
  /** 取引先削除ハンドラ */
  onRemoveClient: (expIndex: number, clientIndex: number) => void;
  /** プロジェクト削除ハンドラ */
  onRemoveProject: (expIndex: number, clientIndex: number, projIndex: number) => void;
  /** プロジェクト編集モーダルを開くハンドラ */
  onOpenProjectModal: (expIndex: number, clientIndex: number, projIndex: number | null) => void;
  /** 職務経歴削除ハンドラ */
  onRemoveExperience: (index: number) => void;
  /** プロジェクトサマリーテキストを生成する関数 */
  projectSummary: (proj: CareerProjectForm) => string;
  /** この経歴の dirty 情報。未指定なら 🔴 表示なし。 */
  dirty?: ExperienceDirty;
};

/**
 * 職務経歴の1件分の編集UIを表示するコンポーネント。
 * CareerResumeForm から職務経歴セクションのロジックを抽出したもの。
 */
export function CareerExperienceEditor({
  exp,
  expIndex,
  onUpdateExperienceField,
  onUpdateClientField,
  onUpdateClientHasClient,
  onUpdateClientIsVacation,
  onUpdateClientVacationIsCurrent,
  onAddClient,
  onRemoveClient,
  onRemoveProject,
  onOpenProjectModal,
  onRemoveExperience,
  projectSummary,
  dirty,
}: CareerExperienceEditorProps) {
  const fieldDirty = dirty?.fields;
  return (
    <div className={shared.entry}>
      <Collapsible
        variant="entry"
        title={
          <>
            {exp.company || "(会社名未入力)"}
            <DirtyDot visible={Boolean(dirty?.any)} />
          </>
        }
      >
        {/* 会社名:事業内容:IT企業 = 4.5:5:0.5 の幅比で配置 */}
        <div className={shared.inline} style={{ gridTemplateColumns: "4.5fr 5fr 0.5fr" }}>
          <label>
            {/* グローバル CSS で label { display: grid } のため、テキストと DirtyDot を span で
              束ねないと別々の行になる。span で 1 グリッド行に束ねることでラベル右側に並べる。 */}
            <span className={shared.labelText}>
              会社名
              <span className={shared.requiredBadge}>必須</span>
              <DirtyDot visible={Boolean(fieldDirty?.company)} />
            </span>
            <input
              type="text"
              value={exp.company}
              onChange={(e) => onUpdateExperienceField(expIndex, "company", e.target.value)}
            />
          </label>
          <label>
            <span className={shared.labelText}>
              事業内容
              <span className={shared.requiredBadge}>必須</span>
              <DirtyDot visible={Boolean(fieldDirty?.business_description)} />
            </span>
            <input
              type="text"
              value={exp.business_description}
              onChange={(e) =>
                onUpdateExperienceField(expIndex, "business_description", e.target.value)
              }
              placeholder="例: SES事業、受託開発"
            />
          </label>
          {/* IT企業かどうか（非ITは取引先を持たず詳細のみ）。会社名・事業内容と同じ行に配置。
              上段は labelText のスペーサで隣のラベル行と高さを合わせ、下段のトグルを入力欄と横並びにする。 */}
          <label>
            <span className={shared.labelText} aria-hidden="true">
              &nbsp;
            </span>
            <span className={styles.companyTypeToggle}>
              <input
                type="checkbox"
                checked={exp.is_it_company}
                onChange={(e) =>
                  onUpdateExperienceField(expIndex, "is_it_company", e.target.checked)
                }
              />
              <span>
                IT企業
                <DirtyDot visible={Boolean(fieldDirty?.is_it_company)} />
              </span>
            </span>
          </label>
        </div>

        <div className={shared.inline}>
          <label>
            <span className={shared.labelText}>
              開始
              <span className={shared.requiredBadge}>必須</span>
              <DirtyDot visible={Boolean(fieldDirty?.start_date)} />
            </span>
            <input
              type="month"
              value={exp.start_date}
              onChange={(e) => onUpdateExperienceField(expIndex, "start_date", e.target.value)}
            />
          </label>
          <label>
            <span>
              在職の有無
              <DirtyDot visible={Boolean(fieldDirty?.is_current)} />
            </span>
            <select
              value={exp.is_current ? "current" : "ended"}
              onChange={(e) =>
                onUpdateExperienceField(expIndex, "is_current", e.target.value === "current")
              }
            >
              <option value="ended">離職</option>
              <option value="current">在職</option>
            </select>
          </label>
          {!exp.is_current && (
            <label>
              <span className={shared.labelText}>
                離職年月
                <span className={shared.requiredBadge}>必須</span>
                <DirtyDot visible={Boolean(fieldDirty?.end_date)} />
              </span>
              <input
                type="month"
                value={exp.end_date}
                onChange={(e) => onUpdateExperienceField(expIndex, "end_date", e.target.value)}
              />
            </label>
          )}
        </div>
        {validateDateRange(exp.start_date, exp.end_date, exp.is_current) && (
          <p className={shared.error} style={{ fontSize: "0.85rem" }}>
            {validateDateRange(exp.start_date, exp.end_date, exp.is_current)}
          </p>
        )}

        <div className={shared.inline}>
          <label>
            <span>
              従業員数
              <DirtyDot visible={Boolean(fieldDirty?.employee_count)} />
            </span>
            <div className={styles.inputWithUnit}>
              <input
                type="number"
                min="0"
                step="1"
                value={exp.employee_count}
                onChange={(e) =>
                  onUpdateExperienceField(expIndex, "employee_count", e.target.value)
                }
                placeholder="例: 300"
              />
              <span className={styles.unit}>名</span>
            </div>
          </label>
          <label>
            <span>
              資本金
              <DirtyDot visible={Boolean(fieldDirty?.capital || fieldDirty?.capital_unit)} />
            </span>
            <div className={styles.inputWithUnit}>
              <input
                type="number"
                min="0"
                value={exp.capital}
                onChange={(e) => onUpdateExperienceField(expIndex, "capital", e.target.value)}
                placeholder="例: 5"
              />
              <select
                className={styles.unitSelect}
                value={exp.capital_unit}
                onChange={(e) => onUpdateExperienceField(expIndex, "capital_unit", e.target.value)}
                aria-label="資本金の単位"
              >
                {CAPITAL_UNITS.map((unit) => (
                  <option key={unit} value={unit}>
                    {unit}
                  </option>
                ))}
              </select>
            </div>
          </label>
        </div>

        {!exp.is_it_company && (
          <div className={styles.stackSection}>
            <label>
              <span className={shared.labelText}>
                詳細
                <span className={shared.requiredBadge}>必須</span>
                <DirtyDot visible={Boolean(fieldDirty?.description)} />
              </span>
              <textarea
                value={exp.description}
                onChange={(e) =>
                  onUpdateExperienceField(expIndex, "description", e.target.value)
                }
                rows={6}
                placeholder="例: 店舗運営・在庫管理・スタッフ教育を担当…"
              />
            </label>
          </div>
        )}

        {exp.is_it_company && (
          <div className={styles.stackSection}>
            <h3>案件情報</h3>
            {exp.clients.map((client, clientIndex) => (
              <ClientEditor
                key={`client-${expIndex}-${clientIndex}`}
                client={client}
                expIndex={expIndex}
                clientIndex={clientIndex}
                dirty={dirty?.clients?.[clientIndex]}
                onUpdateClientField={onUpdateClientField}
                onUpdateClientHasClient={onUpdateClientHasClient}
                onUpdateClientIsVacation={onUpdateClientIsVacation}
                onUpdateClientVacationIsCurrent={onUpdateClientVacationIsCurrent}
                onRemoveProject={onRemoveProject}
                onOpenProjectModal={onOpenProjectModal}
                onRemoveClient={onRemoveClient}
                projectSummary={projectSummary}
              />
            ))}
            <button type="button" className="ghost" onClick={() => onAddClient(expIndex)}>
              取引先を追加
            </button>
          </div>
        )}

        <button type="button" className="danger" onClick={() => onRemoveExperience(expIndex)}>
          職務経歴を削除
        </button>
      </Collapsible>
    </div>
  );
}
