import { useEffect, useRef } from "react";

import type { CareerProjectForm, CareerProjectPeriodForm } from "../../payloadBuilders";
import {
  careerTechnologyStackCategories,
  careerTechnologyStackCategoryLabels,
  phaseOptions,
  teamRoleOptions,
} from "../../constants";
import type { CareerProjectPeriodFieldKey } from "../../formTypes";
import { useProjectModalForm } from "../../hooks/career/useProjectModalForm";
import { useFocusOnMatch } from "../../hooks/useFocusOnMatch";
import type { UseResumeImportAssistReturn } from "../../hooks/career/useResumeImportAssist";
import { Combobox } from "./Combobox";
import { MarkdownTextarea } from "./MarkdownTextarea";
import { ModalShell } from "../ui/ModalShell";
import shared from "../../styles/shared.module.css";
import styles from "./ProjectModal.module.css";

type ProjectModalProps = {
  /** 編集対象のプロジェクト（nullの場合は新規追加） */
  project: CareerProjectForm | null;
  /** 入力反映コールバック。入力のたびに呼ばれ、即時に親フォーム（formCache）へ反映される */
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
  /**
   * バリデーション失敗時に自動フォーカスする期間入力の指定。
   * `CareerExperienceSection` が保存エラー検出時にモーダルを開いて渡す。
   */
  autoFocus?: { periodIndex: number; field: "start_date" | "end_date" };
};

/** プロジェクト期間 1 行分の入力。期間は可変長のため別コンポーネントにして focus hook を使う。 */
type ProjectPeriodRowProps = {
  period: CareerProjectPeriodForm;
  periodIndex: number;
  canRemove: boolean;
  autoFocus?: { periodIndex: number; field: "start_date" | "end_date" };
  onUpdate: (
    periodIndex: number,
    key: CareerProjectPeriodFieldKey,
    value: string | boolean,
  ) => void;
  onRemove: (periodIndex: number) => void;
};

function ProjectPeriodRow({
  period,
  periodIndex,
  canRemove,
  autoFocus,
  onUpdate,
  onRemove,
}: ProjectPeriodRowProps) {
  const startInvalid = autoFocus?.periodIndex === periodIndex && autoFocus.field === "start_date";
  const endInvalid = autoFocus?.periodIndex === periodIndex && autoFocus.field === "end_date";
  const startRef = useFocusOnMatch<HTMLInputElement>(startInvalid);
  const endRef = useFocusOnMatch<HTMLInputElement>(endInvalid);

  return (
    <div className={styles.inline}>
      <label>
        <span className={shared.labelText}>
          開始
          <span className={shared.requiredBadge}>必須</span>
        </span>
        <input
          ref={startRef}
          type="month"
          value={period.start_date}
          onChange={(e) => onUpdate(periodIndex, "start_date", e.target.value)}
          aria-invalid={startInvalid || undefined}
        />
      </label>
      <label>
        <span>参画状況</span>
        <select
          value={period.is_current ? "current" : "ended"}
          onChange={(e) => onUpdate(periodIndex, "is_current", e.target.value === "current")}
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
            ref={endRef}
            type="month"
            value={period.end_date}
            onChange={(e) => onUpdate(periodIndex, "end_date", e.target.value)}
            aria-invalid={endInvalid || undefined}
          />
        </label>
      )}
      {canRemove && (
        <button
          type="button"
          className={styles.chipRemove}
          onClick={() => onRemove(periodIndex)}
          aria-label="期間を削除"
        >
          &times;
        </button>
      )}
    </div>
  );
}

export function ProjectModal({
  project,
  onSave,
  onClose,
  techStackNamesByCategory,
  assist,
  autoFocus,
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

  // 入力のたびに親フォーム（formCache）へ即時反映する。
  // マウント時スナップショットと参照等価で「未編集」を判定し、開いて触らず閉じた場合は
  // 一切コミットしない（= 新規プロジェクトの空レコード生成や StrictMode 二重実行による誤コミットを防ぐ）。
  const initialRef = useRef(local);
  useEffect(() => {
    if (local === initialRef.current) return;
    onSave(local);
    // onSave は親の再生成で identity が変わるため依存に含めず、local 変化のみで発火させる。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [local]);

  return (
    <ModalShell
      title={project ? "プロジェクト編集" : "プロジェクト追加"}
      onClose={onClose}
      assist={assist}
    >
      <label>
        <span>プロジェクト名</span>
        <input
          type="text"
          value={local.name}
          onChange={(e) => updateField("name", e.target.value)}
          placeholder="例: エネルギー業界 IoT Web API アプリ新規開発"
        />
      </label>

      <div className={styles.stackSection}>
        <h3>期間</h3>
        {local.periods.map((period, periodIndex) => (
          <ProjectPeriodRow
            key={`period-${periodIndex}`}
            period={period}
            periodIndex={periodIndex}
            canRemove={local.periods.length > 1}
            autoFocus={autoFocus}
            onUpdate={updatePeriodField}
            onRemove={removePeriod}
          />
        ))}
        <button type="button" className={`ghost ${styles.chipAdd}`} onClick={addPeriod}>
          + 期間を追加
        </button>
      </div>
      {dateError && (
        <p style={{ margin: 0, color: "var(--error)", fontSize: "0.85rem" }}>{dateError}</p>
      )}

      <label>
        <span>役割</span>
        <input
          type="text"
          value={local.role}
          onChange={(e) => updateField("role", e.target.value)}
          placeholder="例: アジャイル開発メンバー"
        />
      </label>

      {/* 体制 */}
      <div className={styles.stackSection}>
        <h3>体制</h3>
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
      />

      {/* スキルセット */}
      <div className={styles.stackSection}>
        <h3>スキルセット ※プルダウンにないものはテキストで入力できます。</h3>
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
        <h3>工程</h3>
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
    </ModalShell>
  );
}
