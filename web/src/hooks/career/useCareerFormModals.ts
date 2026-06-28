import { useState } from "react";

/**
 * CareerResumeForm のモーダル開閉状態とその操作ハンドラをまとめるカスタムフック。
 * 削除確認・マークダウンフィールド編集の 2 モーダルを 1 フックで集約する。
 */
export function useCareerFormModals({
  deleteDoc,
}: {
  deleteDoc: (...args: never[]) => Promise<unknown>;
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [editingField, setEditingField] = useState<"career_summary" | "self_pr" | null>(null);

  const handleDelete = async () => {
    await deleteDoc();
    setShowDeleteConfirm(false);
  };

  return {
    showDeleteConfirm,
    setShowDeleteConfirm,
    editingField,
    setEditingField,
    handleDelete,
  };
}
