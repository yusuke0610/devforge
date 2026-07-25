import { useRef, useState } from "react";

import type { ResumeImportResponse } from "../../api/types";
import { RESUME_IMPORT_MESSAGES } from "../../constants/messages";
import { useResumeImport } from "../../hooks/useResumeImport";
import type { CareerFormState } from "../../payloadBuilders";
import { applyResumeImportToForm, hasCareerFormContent } from "../../utils/resumeImport";
import { ConfirmDialog } from "../ConfirmDialog";
import { InlineSpinner } from "../ui/InlineSpinner";
import { useAppErrorToast, useToast } from "../ui/toast";
import styles from "./ResumeImportPanel.module.css";

type Props = {
  form: CareerFormState;
  /** 抽出結果を反映する setForm（CareerResumeForm の setFormAndClearFocus）。 */
  onApply: (updater: (prev: CareerFormState) => CareerFormState) => void;
  /** 未ログイン時はアップロードせずログイン導線へ流す。 */
  isAuthenticated: boolean;
  requestLogin: () => void;
};

/**
 * 手持ち PDF 経歴書のアップロード → 抽出 → フォーム反映の導線（ADR-0024 / #528）。
 *
 * 空フォームの新規ユーザ向けにフォーム上部へ置く。抽出結果はフォーム state に注入するだけで
 * DB は更新しない（ADR-0010）。入力途中データがある場合は上書き確認ダイアログを挟む。
 */
export function ResumeImportPanel({ form, onApply, isAuthenticated, requestLogin }: Props) {
  const { importing, error, importPdf, clearError } = useResumeImport();
  const { showSuccess, showError } = useToast();
  useAppErrorToast(error);
  const inputRef = useRef<HTMLInputElement>(null);
  // 上書き確認待ちの抽出結果（入力途中データがあるときだけセットする）
  const [pending, setPending] = useState<ResumeImportResponse | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const applyPayload = (payload: ResumeImportResponse) => {
    onApply((prev) => applyResumeImportToForm(prev, payload));
    showSuccess(RESUME_IMPORT_MESSAGES.APPLIED_TOAST);
  };

  const handleFile = async (file: File) => {
    // 抽出中は新規アップロードを受け付けない（応答の順序逆転による誤反映を防止）
    if (importing) return;
    clearError();
    const isPdf =
      file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
    if (!isPdf) {
      showError(RESUME_IMPORT_MESSAGES.INVALID_FILE);
      return;
    }
    const payload = await importPdf(file);
    if (!payload) return; // 失敗時は useAppErrorToast がエラーを表示済み
    if (hasCareerFormContent(form)) {
      setPending(payload);
    } else {
      applyPayload(payload);
    }
  };

  const openFileDialog = () => {
    // 抽出中の再選択を防ぐ（応答の順序逆転による誤反映を防止）
    if (importing) return;
    if (!isAuthenticated) {
      requestLogin();
      return;
    }
    inputRef.current?.click();
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (importing) return;
    if (!isAuthenticated) {
      requestLogin();
      return;
    }
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  };

  return (
    <section className={styles.panel} aria-label={RESUME_IMPORT_MESSAGES.HEADING}>
      <div className={styles.header}>
        <h2 className={styles.title}>{RESUME_IMPORT_MESSAGES.HEADING}</h2>
      </div>
      <p className={styles.hint}>{RESUME_IMPORT_MESSAGES.HINT}</p>

      <div
        className={`${styles.dropzone} ${dragOver ? styles.dragOver : ""}`}
        onClick={openFileDialog}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
        aria-disabled={importing}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            openFileDialog();
          }
        }}
      >
        {importing ? (
          <span className={styles.importing}>
            <InlineSpinner />
            {RESUME_IMPORT_MESSAGES.IMPORTING}
          </span>
        ) : (
          <>
            <span className={styles.dropHint}>{RESUME_IMPORT_MESSAGES.DROP_HINT}</span>
            <span className={styles.uploadLabel}>{RESUME_IMPORT_MESSAGES.UPLOAD_LABEL}</span>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        aria-label={RESUME_IMPORT_MESSAGES.UPLOAD_LABEL}
        className={styles.fileInput}
        onChange={(e) => {
          const file = e.target.files?.[0];
          // 同じファイルを連続選択しても onChange が発火するよう value をリセットする
          e.target.value = "";
          if (file) void handleFile(file);
        }}
      />

      {pending && (
        <ConfirmDialog
          message={RESUME_IMPORT_MESSAGES.OVERWRITE_CONFIRM}
          confirmLabel={RESUME_IMPORT_MESSAGES.OVERWRITE_CONFIRM_LABEL}
          onConfirm={() => {
            applyPayload(pending);
            setPending(null);
          }}
          onCancel={() => setPending(null)}
        />
      )}
    </section>
  );
}
