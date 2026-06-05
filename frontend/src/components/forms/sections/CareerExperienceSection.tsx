import { useEffect, useMemo } from "react";
import type { Dispatch, SetStateAction } from "react";

import type { ExperienceDirty } from "../../../hooks/career/useCareerDirty";
import type {
  CareerExperienceForm,
  CareerFieldLocator,
  CareerFormState,
  CareerProjectForm,
} from "../../../payloadBuilders";
import type { TechStackMasterItem } from "../../../api/types";
import { useCareerExperienceMutators } from "../../../hooks/career/useCareerExperienceMutators";
import { useProjectModalState } from "../../../hooks/career/useProjectModalState";
import type { UseResumeImportAssistReturn } from "../../../hooks/career/useResumeImportAssist";
import shared from "../../../styles/shared.module.css";
import styles from "../CareerResumeForm.module.css";
import { CareerExperienceEditor } from "../CareerFormEditors/CareerExperienceEditor";
import { ProjectModal } from "../ProjectModal";
import { DirtyDot } from "../../ui/DirtyDot";
import { PlusIcon } from "../../icons/PlusIcon";

/** CareerExperienceSection のプロパティ型 */
type CareerExperienceSectionProps = {
  /** 職務経歴データの配列 */
  experiences: CareerExperienceForm[];
  /** フォーム状態更新ディスパッチャ */
  setForm: Dispatch<SetStateAction<CareerFormState>>;
  /** 技術スタックのマスタデータ */
  techStackOptions: TechStackMasterItem[];
  /** 各経歴の dirty 情報。要素数は experiences と一致する想定。 */
  experiencesDirty?: ExperienceDirty[];
  /** 「職務経歴」セクション全体の未保存集約フラグ */
  sectionDirty?: boolean;
  /** PDF 取り込み補助。プロジェクトモーダル内に取り込みパネルを再掲するため受け渡す */
  assist?: UseResumeImportAssistReturn;
  /** バリデーション失敗フィールドの位置情報（フォーカス・赤枠・折りたたみ展開用） */
  focusLocator?: CareerFieldLocator | null;
  /** フォーカス発火の nonce（折りたたみ自動展開の再発火鍵） */
  focusNonce?: number;
};

/**
 * 職務経歴書の職務経歴セクション。
 * 更新ロジックは useCareerExperienceMutators に委譲し、
 * モーダル管理は useProjectModalState に委譲する。
 */
export function CareerExperienceSection({
  experiences,
  setForm,
  techStackOptions,
  experiencesDirty,
  sectionDirty = false,
  assist,
  focusLocator = null,
  focusNonce = 0,
}: CareerExperienceSectionProps) {
  /** カテゴリごとの技術スタック名称マップを生成する */
  const techStackNamesByCategory = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const item of techStackOptions) {
      const list = map.get(item.category) ?? [];
      list.push(item.name);
      map.set(item.category, list);
    }
    return map;
  }, [techStackOptions]);

  const mutators = useCareerExperienceMutators(experiences, setForm);

  const { modalTarget, setModalTarget, modalProject, handleProjectSave, closeModal } =
    useProjectModalState(mutators.getProject, mutators.onProjectSave);

  // プロジェクト配下のバリデーションエラー時は該当プロジェクトのモーダルを自動で開く。
  // focusLocator は保存のたびに新しい参照になるため、同じプロジェクトでも再発火する。
  useEffect(() => {
    if (focusLocator?.kind === "project") {
      setModalTarget({
        expIndex: focusLocator.expIndex,
        clientIndex: focusLocator.clientIndex,
        projIndex: focusLocator.projIndex,
      });
    }
    // setModalTarget は state setter で安定。focusLocator の変化のみで発火させる。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusLocator]);

  // 開いているモーダルが該当プロジェクトなら、フォーカスすべき期間入力を渡す。
  const projectAutoFocus =
    modalTarget &&
    focusLocator?.kind === "project" &&
    focusLocator.expIndex === modalTarget.expIndex &&
    focusLocator.clientIndex === modalTarget.clientIndex &&
    focusLocator.projIndex === modalTarget.projIndex
      ? { periodIndex: focusLocator.periodIndex, field: focusLocator.field }
      : undefined;

  /** プロジェクトの期間サマリーテキストを生成する（複数期間は「、」区切り） */
  const projectSummary = (proj: CareerProjectForm) => {
    return proj.periods
      .map((p) => {
        const end = p.is_current ? "現在" : p.end_date;
        return [p.start_date, end].filter(Boolean).join(" 〜 ");
      })
      .filter(Boolean)
      .join("、");
  };

  /** モーダルを開くハンドラ */
  const handleOpenProjectModal = (
    expIndex: number,
    clientIndex: number,
    projIndex: number | null,
  ) => {
    setModalTarget({ expIndex, clientIndex, projIndex });
  };

  return (
    <section className={shared.section}>
      {modalTarget && (
        <ProjectModal
          project={modalProject}
          onSave={handleProjectSave}
          onClose={closeModal}
          techStackNamesByCategory={techStackNamesByCategory}
          assist={assist}
          autoFocus={projectAutoFocus}
        />
      )}

      <h2>
        職務経歴
        <DirtyDot visible={sectionDirty} />
      </h2>
      {experiences.map((exp, expIndex) => (
        <CareerExperienceEditor
          key={`exp-${expIndex}`}
          exp={exp}
          expIndex={expIndex}
          onUpdateExperienceField={mutators.updateExperienceField}
          onUpdateClientField={mutators.updateClientField}
          onUpdateClientHasClient={mutators.updateClientHasClient}
          onUpdateClientIsVacation={mutators.updateClientIsVacation}
          onUpdateClientVacationIsCurrent={mutators.updateClientVacationIsCurrent}
          onAddClient={mutators.addClient}
          onRemoveClient={mutators.removeClient}
          onRemoveProject={mutators.removeProject}
          onOpenProjectModal={handleOpenProjectModal}
          onRemoveExperience={mutators.removeExperience}
          projectSummary={projectSummary}
          dirty={experiencesDirty?.[expIndex]}
          focusLocator={focusLocator}
          focusNonce={focusNonce}
        />
      ))}

      <button
        type="button"
        className={`ghost ${styles.addButton}`}
        onClick={mutators.addExperience}
      >
        <PlusIcon />
        職務経歴を追加
      </button>
    </section>
  );
}
