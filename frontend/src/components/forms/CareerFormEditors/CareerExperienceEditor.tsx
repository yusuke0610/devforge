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
        <div className={shared.inline}>
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

        {/* IT企業かどうか（非ITは取引先を持たず詳細のみ） */}
        <label className={styles.clientCheckbox}>
          <input
            type="checkbox"
            checked={exp.is_it_company}
            onChange={(e) => onUpdateExperienceField(expIndex, "is_it_company", e.target.checked)}
          />
          <span>
            IT企業
            <DirtyDot visible={Boolean(fieldDirty?.is_it_company)} />
          </span>
        </label>

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
            <h3>取引先</h3>
            {exp.clients.map((client, clientIndex) => {
              const clientDirty = dirty?.clients?.[clientIndex];
              return (
                <div key={`client-${expIndex}-${clientIndex}`} className={shared.entry}>
                  <div className={styles.clientHeader}>
                    {!client.is_vacation && client.has_client && (
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
                    {!client.is_vacation && (
                      <label className={styles.clientCheckbox}>
                        <input
                          type="checkbox"
                          checked={!client.has_client}
                          onChange={(e) =>
                            onUpdateClientHasClient(expIndex, clientIndex, !e.target.checked)
                          }
                        />
                        {/* has_client=false で name 入力が消えた時にも未保存状態を可視化するため
                          常時表示のチェックボックス側にも dot を出す。 */}
                        <span>
                          取引先なし
                          <DirtyDot visible={Boolean(clientDirty?.self)} />
                        </span>
                      </label>
                    )}
                    <label className={styles.clientCheckbox}>
                      <input
                        type="checkbox"
                        checked={client.is_vacation}
                        onChange={(e) =>
                          onUpdateClientIsVacation(expIndex, clientIndex, e.target.checked)
                        }
                      />
                      <span>
                        休暇
                        <DirtyDot visible={Boolean(clientDirty?.self)} />
                      </span>
                    </label>
                  </div>

                  {client.is_vacation ? (
                    /* 休暇: 期間 + 詳細 */
                    <div className={styles.stackSection}>
                      <div className={shared.inline}>
                        <label>
                          <span className={shared.labelText}>
                            開始
                            <span className={shared.requiredBadge}>必須</span>
                          </span>
                          <input
                            type="month"
                            value={client.vacation_start_date}
                            onChange={(e) =>
                              onUpdateClientField(
                                expIndex,
                                clientIndex,
                                "vacation_start_date",
                                e.target.value,
                              )
                            }
                          />
                        </label>
                        <label>
                          <span>継続の有無</span>
                          <select
                            value={client.vacation_is_current ? "current" : "ended"}
                            onChange={(e) =>
                              onUpdateClientVacationIsCurrent(
                                expIndex,
                                clientIndex,
                                e.target.value === "current",
                              )
                            }
                          >
                            <option value="ended">終了</option>
                            <option value="current">継続中</option>
                          </select>
                        </label>
                        {!client.vacation_is_current && (
                          <label>
                            <span className={shared.labelText}>
                              終了
                              <span className={shared.requiredBadge}>必須</span>
                            </span>
                            <input
                              type="month"
                              value={client.vacation_end_date}
                              onChange={(e) =>
                                onUpdateClientField(
                                  expIndex,
                                  clientIndex,
                                  "vacation_end_date",
                                  e.target.value,
                                )
                              }
                            />
                          </label>
                        )}
                      </div>
                      {validateDateRange(
                        client.vacation_start_date,
                        client.vacation_end_date,
                        client.vacation_is_current,
                      ) && (
                        <p className={shared.error} style={{ fontSize: "0.85rem" }}>
                          {validateDateRange(
                            client.vacation_start_date,
                            client.vacation_end_date,
                            client.vacation_is_current,
                          )}
                        </p>
                      )}
                      <label>
                        <span className={shared.labelText}>詳細</span>
                        <textarea
                          value={client.vacation_description}
                          onChange={(e) =>
                            onUpdateClientField(
                              expIndex,
                              clientIndex,
                              "vacation_description",
                              e.target.value,
                            )
                          }
                          rows={4}
                          placeholder="例: 育児休暇を取得。期間中にProgateでJavaScriptを学習…"
                        />
                      </label>
                    </div>
                  ) : (
                    /* プロジェクト一覧（サマリー表示） */
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
                                onClick={() =>
                                  onOpenProjectModal(expIndex, clientIndex, projIndex)
                                }
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
                  )}

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
        )}

        <button type="button" className="danger" onClick={() => onRemoveExperience(expIndex)}>
          職務経歴を削除
        </button>
      </Collapsible>
    </div>
  );
}
