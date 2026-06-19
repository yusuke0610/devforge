import { useState } from "react";

import type { CareerProjectForm } from "../../payloadBuilders";

/** プロジェクトモーダルの対象を表す型 */
export type ProjectModalTarget = {
  expIndex: number;
  clientIndex: number;
  /** null の場合は新規追加 */
  projIndex: number | null;
};

/**
 * CareerResumeForm の ProjectModal 状態管理を担うカスタムフック。
 * モーダルの開閉・対象プロジェクトの算出・入力反映ハンドラを提供する。
 */
export function useProjectModalState(
  getProject: (expIndex: number, clientIndex: number, projIndex: number) => CareerProjectForm | null,
  onSave: (expIndex: number, clientIndex: number, projIndex: number | null, project: CareerProjectForm) => void,
  getProjectCount: (expIndex: number, clientIndex: number) => number,
) {
  const [modalTarget, setModalTarget] = useState<ProjectModalTarget | null>(null);

  /**
   * モーダルに渡す現在のプロジェクトデータを取得する。
   * 新規追加の場合は null を返す。
   */
  const modalProject: CareerProjectForm | null = modalTarget
    ? modalTarget.projIndex !== null
      ? getProject(modalTarget.expIndex, modalTarget.clientIndex, modalTarget.projIndex)
      : null
    : null;

  /**
   * モーダルの入力反映コールバック。入力のたびに呼ばれ、即時にフォームへ反映する（モーダルは閉じない）。
   * 新規プロジェクト（projIndex===null）は初回反映時に 1 度だけ末尾へ追加し、
   * 確定した実 index を modalTarget に反映する。以後は同じ index を更新するため、
   * 入力のたびに新しい空レコードが増えることはない。
   */
  const handleProjectSave = (project: CareerProjectForm) => {
    if (!modalTarget) return;
    const { expIndex, clientIndex, projIndex } = modalTarget;
    if (projIndex === null) {
      const newIndex = getProjectCount(expIndex, clientIndex);
      onSave(expIndex, clientIndex, null, project);
      setModalTarget({ expIndex, clientIndex, projIndex: newIndex });
    } else {
      onSave(expIndex, clientIndex, projIndex, project);
    }
  };

  /** モーダルを閉じる。 */
  const closeModal = () => setModalTarget(null);

  return {
    modalTarget,
    setModalTarget,
    modalProject,
    handleProjectSave,
    closeModal,
  };
}
