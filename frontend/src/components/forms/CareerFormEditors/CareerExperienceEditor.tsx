import type { CareerClientFieldKey, CareerExperienceFieldKey } from "../../../formTypes";
import type { ExperienceDirty } from "../../../hooks/career/useCareerDirty";
import {
  validateDateRange,
  type CareerExperienceForm,
  type CareerProjectForm,
} from "../../../payloadBuilders";
import shared from "../../../styles/shared.module.css";
import styles from "../CareerResumeForm.module.css";
import { DirtyDot } from "../../ui/DirtyDot";

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
      <div className={shared.inline}>
        <label>
          {/* グローバル CSS で label { display: grid } のため、テキストと DirtyDot を span で
              束ねないと別々の行になる。span で 1 グリッド行に束ねることでラベル右側に並べる。 */}
          <span>
            会社名
            <DirtyDot visible={Boolean(fieldDirty?.company)} />
          </span>
          <input
            type="text"
            value={exp.company}
            onChange={(e) => onUpdateExperienceField(expIndex, "company", e.target.value)}
          />
        </label>
        <label>
          <span>
            事業内容
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
      </div>

      <div className={shared.inline}>
        <label>
          <span>
            開始
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
            <span>
              離職年月
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
            <DirtyDot visible={Boolean(fieldDirty?.capital)} />
          </span>
          <div className={styles.inputWithUnit}>
            <input
              type="number"
              value={exp.capital}
              onChange={(e) => onUpdateExperienceField(expIndex, "capital", e.target.value)}
              placeholder="例: 5"
            />
            <span className={styles.unit}>千万円</span>
          </div>
        </label>
      </div>

      {/* 取引先 */}
      <div className={styles.stackSection}>
        <h3>取引先</h3>
        {exp.clients.map((client, clientIndex) => {
          const clientDirty = dirty?.clients?.[clientIndex];
          return (
            <div key={`client-${expIndex}-${clientIndex}`} className={shared.entry}>
              <div className={styles.clientHeader}>
                {client.has_client && (
                  <label className={styles.clientNameLabel}>
                    <span>
                      取引先名（呼称）
                      <DirtyDot visible={Boolean(clientDirty?.self)} />
                    </span>
                    <input
                      type="text"
                      value={client.name}
                      onChange={(e) =>
                        onUpdateClientField(expIndex, clientIndex, "name", e.target.value)
                      }
                      placeholder="例: 〇〇社（略称）"
                    />
                  </label>
                )}
                <label className={styles.clientCheckbox}>
                  <input
                    type="checkbox"
                    checked={!client.has_client}
                    onChange={(e) =>
                      onUpdateClientHasClient(expIndex, clientIndex, !e.target.checked)
                    }
                  />
                  取引先なし
                </label>
              </div>

              {/* プロジェクト一覧（サマリー表示） */}
              <div className={styles.stackSection}>
                <h3>プロジェクト</h3>
                {client.projects.map((proj, projIndex) => {
                  const projDirty = clientDirty?.projects?.[projIndex];
                  return (
                    <div
                      key={`proj-${expIndex}-${clientIndex}-${projIndex}`}
                      className={styles.projectSummaryRow}
                    >
                      <span className={styles.projectName}>
                        {proj.name || "(未入力)"}
                        <DirtyDot visible={Boolean(projDirty?.any)} />
                      </span>
                      <span className={styles.projectPeriod}>{projectSummary(proj)}</span>
                      <div className={styles.projectActions}>
                        <button
                          type="button"
                          onClick={() => onOpenProjectModal(expIndex, clientIndex, projIndex)}
                        >
                          編集
                        </button>
                        <button
                          type="button"
                          className="danger"
                          onClick={() => onRemoveProject(expIndex, clientIndex, projIndex)}
                        >
                          削除
                        </button>
                      </div>
                    </div>
                  );
                })}
                <button
                  type="button"
                  className="ghost"
                  onClick={() => onOpenProjectModal(expIndex, clientIndex, null)}
                >
                  プロジェクトを追加
                </button>
              </div>

              <button
                type="button"
                className="danger"
                onClick={() => onRemoveClient(expIndex, clientIndex)}
              >
                取引先を削除
              </button>
            </div>
          );
        })}
        <button type="button" className="ghost" onClick={() => onAddClient(expIndex)}>
          取引先を追加
        </button>
      </div>

      <button type="button" className="danger" onClick={() => onRemoveExperience(expIndex)}>
        職務経歴を削除
      </button>
    </div>
  );
}
