import { useRef, type CSSProperties } from "react";

import type { CareerProjectForm } from "../../payloadBuilders";
import {
  careerTechnologyStackCategories,
  careerTechnologyStackCategoryLabels,
  phaseOptions,
  teamRoleOptions,
} from "../../constants";
import { useProjectFormDirty } from "../../hooks/career/useProjectFormDirty";
import { useProjectModalForm } from "../../hooks/career/useProjectModalForm";
import { useImportPanelLayout } from "../../hooks/career/useImportPanelLayout";
import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";
import { Combobox } from "./Combobox";
import { MarkdownTextarea } from "./MarkdownTextarea";
import { ResumeSourceTracePanel } from "./ResumeSourceTracePanel";
import { DirtyDot } from "../ui/DirtyDot";
import shared from "../../styles/shared.module.css";
import styles from "./ProjectModal.module.css";

type ProjectModalProps = {
  /** 編集対象のプロジェクト（nullの場合は新規追加） */
  project: CareerProjectForm | null;
  /** 保存時のコールバック */
  onSave: (project: CareerProjectForm) => void;
  /** 閉じるコールバック */
  onClose: () => void;
  /** カテゴリごとのスキルセット名称リスト */
  techStackNamesByCategory: Map<string, string[]>;
  /**
   * PDF 取り込み補助。PDF が選択されている時はモーダル内の右カラムに原本ビューを再掲する。
   * モーダルのオーバーレイ（position:fixed）が画面右の本体パネルを覆ってクリックを
   * 奪うため、子モーダルを開いている間でも流し込めるようモーダル内に再掲する。
   */
  assist?: UseResumeImportAssistReturn;
};

export function ProjectModal({
  project,
  onSave,
  onClose,
  techStackNamesByCategory,
  assist,
}: ProjectModalProps) {
  const {
    local,
    dateError,
    updateField,
    addPeriod,
    removePeriod,
    updatePeriodField,
    updateTechStack,
    addTechStack,
    removeTechStack,
    updateTeamTotal,
    addTeamMember,
    removeTeamMember,
    updateTeamMember,
    togglePhase,
  } = useProjectModalForm(project);

  /** モーダル内編集の dirty 判定（元データとの差分） */
  const dirty = useProjectFormDirty(local, project);

  /** PDF が選択されている時だけモーダル内に原本ビューを表示する */
  const showPdf = !!assist && !!assist.file;

  // 入力フォームと PDF カラムの比率をスプリッターのドラッグで変える。
  // PDF カラムは右側なので「幅 = コンテナ右端 - マウス X」。reservedGap はカラム間のスプリッター(6px)。
  const bodyWrapRef = useRef<HTMLDivElement>(null);
  const { width: pdfWidth, startResize } = useImportPanelLayout(bodyWrapRef, {
    initialWidth: 440,
    minWidth: 240,
    minFormWidth: 320,
    reservedGap: 6,
  });

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <span>
            {project ? "プロジェクト編集" : "プロジェクト追加"}
            <DirtyDot visible={dirty.any} />
          </span>
          <div className={styles.headerActions}>
            <button
              type="button"
              className="primary"
              onClick={() => onSave(local)}
              disabled={!!dateError}
            >
              保存
            </button>
            <button type="button" onClick={onClose}>
              キャンセル
            </button>
          </div>
        </div>

        <div
          className={styles.bodyWrap}
          ref={bodyWrapRef}
          style={showPdf ? ({ "--pdf-col-width": `${pdfWidth}px` } as CSSProperties) : undefined}
        >
          <div className={styles.body}>
            <label>
              {/* グローバル CSS の label { display: grid } により、
                テキスト + DirtyDot を span でひとつのグリッド行にまとめる。 */}
              <span>
                プロジェクト名
                <DirtyDot visible={dirty.fields.name} />
              </span>
              <input
                type="text"
                value={local.name}
                onChange={(e) => updateField("name", e.target.value)}
                placeholder="例: エネルギー業界 IoT Web API アプリ新規開発"
              />
            </label>

            <div className={styles.stackSection}>
              <h3>
                期間
                <DirtyDot visible={dirty.periods} />
              </h3>
              {local.periods.map((period, periodIndex) => (
                <div key={`period-${periodIndex}`} className={styles.inline}>
                  <label>
                    <span className={shared.labelText}>
                      開始
                      <span className={shared.requiredBadge}>必須</span>
                    </span>
                    <input
                      type="month"
                      value={period.start_date}
                      onChange={(e) => updatePeriodField(periodIndex, "start_date", e.target.value)}
                    />
                  </label>
                  <label>
                    <span>参画状況</span>
                    <select
                      value={period.is_current ? "current" : "ended"}
                      onChange={(e) =>
                        updatePeriodField(periodIndex, "is_current", e.target.value === "current")
                      }
                    >
                      <option value="ended">終了</option>
                      <option value="current">参画中</option>
                    </select>
                  </label>
                  {!period.is_current && (
                    <label>
                      <span className={shared.labelText}>
                        終了
                        <span className={shared.requiredBadge}>必須</span>
                      </span>
                      <input
                        type="month"
                        value={period.end_date}
                        onChange={(e) =>
                          updatePeriodField(periodIndex, "end_date", e.target.value)
                        }
                      />
                    </label>
                  )}
                  {local.periods.length > 1 && (
                    <button
                      type="button"
                      className={styles.chipRemove}
                      onClick={() => removePeriod(periodIndex)}
                      aria-label="期間を削除"
                    >
                      &times;
                    </button>
                  )}
                </div>
              ))}
              <button type="button" className={`ghost ${styles.chipAdd}`} onClick={addPeriod}>
                + 期間を追加
              </button>
            </div>
            {dateError && (
              <p style={{ margin: 0, color: "var(--error)", fontSize: "0.85rem" }}>{dateError}</p>
            )}

            <label>
              <span>
                役割
                <DirtyDot visible={dirty.fields.role} />
              </span>
              <input
                type="text"
                value={local.role}
                onChange={(e) => updateField("role", e.target.value)}
                placeholder="例: アジャイル開発メンバー"
              />
            </label>

            {/* 体制 */}
            <div className={styles.stackSection}>
              <h3>
                体制
                <DirtyDot visible={dirty.team} />
              </h3>
              <div className={styles.teamLayout}>
                <label className={styles.teamTotal}>
                  <span>全体人数</span>
                  <div className={styles.inputWithUnit}>
                    <input
                      type="number"
                      min="0"
                      value={local.team.total}
                      onChange={(e) => updateTeamTotal(e.target.value)}
                      placeholder="例: 10"
                    />
                    <span className={styles.unit}>名</span>
                  </div>
                </label>

                <button type="button" className={`ghost ${styles.chipAdd}`} onClick={addTeamMember}>
                  + 役割を追加
                </button>

                {local.team.members.map((member, memberIndex) => (
                  <div key={`member-${memberIndex}`} className={styles.stackChip}>
                    <select
                      className={styles.chipSelect}
                      value={member.role}
                      onChange={(e) => updateTeamMember(memberIndex, "role", e.target.value)}
                    >
                      <option value="">選択</option>
                      {teamRoleOptions.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                    <div className={styles.inputWithUnit}>
                      <input
                        type="number"
                        min="0"
                        value={member.count}
                        onChange={(e) => updateTeamMember(memberIndex, "count", e.target.value)}
                        placeholder="人数"
                        style={{ width: "5em" }}
                      />
                      <span className={styles.unit}>名</span>
                    </div>
                    <button
                      type="button"
                      className={styles.chipRemove}
                      onClick={() => removeTeamMember(memberIndex)}
                      aria-label="役割を削除"
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <MarkdownTextarea
              label="詳細"
              value={local.description}
              onChange={(v) => updateField("description", v)}
              rows={6}
              labelAdornment={<DirtyDot visible={dirty.fields.description} />}
            />

            {/* スキルセット */}
            <div className={styles.stackSection}>
              <h3>
                スキルセット ※プルダウンにないものはテキストで入力できます。
                <DirtyDot visible={dirty.technology_stacks} />
              </h3>
              <div className={styles.stackGrid}>
                {local.technology_stacks.map((stack, stackIndex) => (
                  <div key={`stack-${stackIndex}`} className={styles.stackChip}>
                    <select
                      className={styles.chipSelect}
                      value={stack.category}
                      onChange={(e) => updateTechStack(stackIndex, "category", e.target.value)}
                    >
                      {careerTechnologyStackCategories.map((cat) => (
                        <option key={cat} value={cat}>
                          {careerTechnologyStackCategoryLabels[cat]}
                        </option>
                      ))}
                    </select>
                    <Combobox
                      value={stack.name}
                      onChange={(val) => updateTechStack(stackIndex, "name", val)}
                      options={techStackNamesByCategory.get(stack.category) ?? []}
                      placeholder="例: TypeScript"
                      allowCustom
                    />
                    <button
                      type="button"
                      className={styles.chipRemove}
                      onClick={() => removeTechStack(stackIndex)}
                      aria-label="スキルセットを削除"
                    >
                      &times;
                    </button>
                  </div>
                ))}
                <button type="button" className={`ghost ${styles.chipAdd}`} onClick={addTechStack}>
                  + 追加
                </button>
              </div>
            </div>

            {/* 工程 */}
            <div className={styles.stackSection}>
              <h3>
                工程
                <DirtyDot visible={dirty.phases} />
              </h3>
              <div className={styles.phaseList}>
                {phaseOptions.map((phase) => (
                  <label
                    key={`phase-${phase}`}
                    className={styles.stackChip}
                    style={{ cursor: "pointer" }}
                  >
                    <input
                      type="checkbox"
                      checked={local.phases.includes(phase)}
                      onChange={() => togglePhase(phase)}
                    />
                    {phase}
                  </label>
                ))}
              </div>
            </div>
          </div>
          {showPdf && assist && (
            <>
              {/* 入力フォームと PDF カラムの境界。ドラッグで左右比率を変える（縦積み時は CSS で非表示）。 */}
              <div
                className={styles.splitter}
                role="separator"
                aria-orientation="vertical"
                onMouseDown={startResize}
              />
              <aside className={styles.blocksColumn}>
                <ResumeSourceTracePanel assist={assist} />
              </aside>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
