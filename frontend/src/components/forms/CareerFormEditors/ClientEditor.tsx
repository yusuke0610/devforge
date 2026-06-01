import type { CareerClientFieldKey } from "../../../formTypes";
import type { ClientDirty } from "../../../hooks/career/useCareerDirty";
import {
  validateDateRange,
  type CareerClientForm,
  type CareerProjectForm,
} from "../../../payloadBuilders";
import shared from "../../../styles/shared.module.css";
import styles from "../CareerResumeForm.module.css";
import { DirtyDot } from "../../ui/DirtyDot";

/** ClientEditor のプロパティ型 */
type ClientEditorProps = {
  /** 編集対象の取引先データ */
  client: CareerClientForm;
  /** 親となる職務経歴のインデックス */
  expIndex: number;
  /** この取引先のインデックス */
  clientIndex: number;
  /** この取引先の dirty 情報。未指定なら 🔴 表示なし。 */
  dirty?: ClientDirty;
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
  /** プロジェクト削除ハンドラ */
  onRemoveProject: (expIndex: number, clientIndex: number, projIndex: number) => void;
  /** プロジェクト編集モーダルを開くハンドラ */
  onOpenProjectModal: (expIndex: number, clientIndex: number, projIndex: number | null) => void;
  /** 取引先削除ハンドラ */
  onRemoveClient: (expIndex: number, clientIndex: number) => void;
  /** プロジェクトサマリーテキストを生成する関数 */
  projectSummary: (proj: CareerProjectForm) => string;
};

/**
 * IT企業の職務経歴に紐づく取引先1件分の編集UIを表示するコンポーネント。
 * 休暇ブロックとプロジェクト一覧の分岐を担う。
 * CareerExperienceEditor から取引先セクションを抽出したもの。
 */
export function ClientEditor({
  client,
  expIndex,
  clientIndex,
  dirty,
  onUpdateClientField,
  onUpdateClientHasClient,
  onUpdateClientIsVacation,
  onUpdateClientVacationIsCurrent,
  onRemoveProject,
  onOpenProjectModal,
  onRemoveClient,
  projectSummary,
}: ClientEditorProps) {
  return (
    <div className={shared.entry}>
      <div className={styles.clientHeader}>
        {!client.is_vacation && client.has_client && (
          <label className={styles.clientNameLabel}>
            <span>
              案件名
              <DirtyDot visible={Boolean(dirty?.self)} />
            </span>
            <input
              type="text"
              value={client.name}
              onChange={(e) => onUpdateClientField(expIndex, clientIndex, "name", e.target.value)}
              placeholder="例: 〇〇社（略称）"
            />
          </label>
        )}
        {!client.is_vacation && (
          <label className={styles.clientCheckbox}>
            <input
              type="checkbox"
              checked={!client.has_client}
              onChange={(e) => onUpdateClientHasClient(expIndex, clientIndex, !e.target.checked)}
            />
            {/* has_client=false で name 入力が消えた時にも未保存状態を可視化するため
              常時表示のチェックボックス側にも dot を出す。 */}
            <span>
              取引先なし
              <DirtyDot visible={Boolean(dirty?.self)} />
            </span>
          </label>
        )}
        <label className={styles.clientCheckbox}>
          <input
            type="checkbox"
            checked={client.is_vacation}
            onChange={(e) => onUpdateClientIsVacation(expIndex, clientIndex, e.target.checked)}
          />
          <span>
            休暇
            <DirtyDot visible={Boolean(dirty?.self)} />
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
                  onUpdateClientField(expIndex, clientIndex, "vacation_start_date", e.target.value)
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
                    onUpdateClientField(expIndex, clientIndex, "vacation_end_date", e.target.value)
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
                onUpdateClientField(expIndex, clientIndex, "vacation_description", e.target.value)
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
            const projDirty = dirty?.projects?.[projIndex];
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
      )}

      <button
        type="button"
        className="danger"
        onClick={() => onRemoveClient(expIndex, clientIndex)}
      >
        {client.is_vacation ? "休業を削除" : "取引先を削除"}
      </button>
    </div>
  );
}
