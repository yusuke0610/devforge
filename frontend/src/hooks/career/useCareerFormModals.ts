import { useState } from "react";

/**
 * CareerResumeForm のモーダル開閉状態とその操作ハンドラをまとめるカスタムフック。
 * 削除確認・保存確認・マークダウンフィールド編集の 3 モーダルを 1 フックで集約する。
 */
export function useCareerFormModals({
  save,
  deleteDoc,
}: {
  save: (...args: never[]) => Promise<unknown>;
  deleteDoc: (...args: never[]) => Promise<unknown>;
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);
  const [editingField, setEditingField] = useState<"career_summary" | "self_pr" | null>(null);

  const handleDelete = async () => {
    await deleteDoc();
    setShowDeleteConfirm(false);
  };

  const handleConfirmSave = async () => {
    await save();
    setShowSaveConfirm(false);
  };

  return {
    showDeleteConfirm,
    setShowDeleteConfirm,
    showSaveConfirm,
    setShowSaveConfirm,
    editingField,
    setEditingField,
    handleDelete,
    handleConfirmSave,
  };
}
