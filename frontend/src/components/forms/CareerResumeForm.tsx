import { FormEvent, useState } from "react";

import {
  createCareerResume,
  deleteCareerResume,
  downloadCareerResumeMarkdown,
  downloadCareerResumePdf,
  getCareerResumePdfBlobUrl,
  getLatestCareerResume,
  updateCareerResume,
} from "../../api";
import { createInitialCareerForm, mapCareerResumeToForm } from "../../formMappers";
import { useCareerDirty } from "../../hooks/career/useCareerDirty";
import { useDocumentForm } from "../../hooks/useDocumentForm";
import { buildCareerPayload } from "../../payloadBuilders";
import type { CareerTextFieldKey } from "../../formTypes";
import { useQualifications, useTechnologyStacks } from "../../hooks/useMasterData";
import { usePdfActions } from "../../hooks/usePdfActions";
import shared from "../../styles/shared.module.css";
import { ConfirmDialog } from "../ConfirmDialog";
import { DirtyDot } from "../ui/DirtyDot";
import { Skeleton } from "../ui/Skeleton";
import { PdfPreviewModal } from "./PdfPreviewModal";
import { CareerBasicInfoSection } from "./sections/CareerBasicInfoSection";
import { CareerExperienceSection } from "./sections/CareerExperienceSection";
import { CareerQualificationsSection } from "./sections/CareerQualificationsSection";
import { CareerSelfPrSection } from "./sections/CareerSelfPrSection";

export function CareerResumeForm() {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const {
    form,
    setForm,
    baseline,
    documentId: resumeId,
    loading,
    saving,
    deleting,
    error: formError,
    success: formSuccess,
    save,
    deleteDoc,
    saveButtonText,
  } = useDocumentForm({
    createInitialForm: createInitialCareerForm,
    loadLatest: getLatestCareerResume,
    createDocument: createCareerResume,
    updateDocument: updateCareerResume,
    deleteDocument: deleteCareerResume,
    buildPayload: buildCareerPayload,
    mapResponseToForm: mapCareerResumeToForm,
    successMessage: "職務経歴書を保存しました。PDF出力できます。",
    cacheKey: "career",
  });

  const { items: techStackOptions, loading: techLoading } = useTechnologyStacks();
  const { items: qualificationOptions, loading: qualLoading } = useQualifications();
  const qualificationNames = qualificationOptions.map((item) => item.name);

  /** 未保存マーク（🔴）の表示判定に使う dirty マップ */
  const dirty = useCareerDirty(form, baseline);

  const {
    downloading,
    previewUrl,
    closePreview,
    onDownloadPdf,
    onDownloadMarkdown,
    onPreviewPdf,
    error: pdfError,
    success: pdfSuccess,
  } = usePdfActions({
    downloadPdf: downloadCareerResumePdf,
    downloadMarkdown: downloadCareerResumeMarkdown,
    getPdfBlobUrl: getCareerResumePdfBlobUrl,
  });

  /** PDF アクションまたはフォーム保存のエラー・成功メッセージを統合して表示する */
  const error = pdfError ?? formError;
  const success = pdfSuccess ?? formSuccess;

  /** フォームデータ・技術スタック・資格の3つが揃ってから送信可能 */
  const canSubmit = !loading && !techLoading && !qualLoading;

  const onChangeField = (key: CareerTextFieldKey, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await save();
  };

  const handleDelete = async () => {
    await deleteDoc();
    setShowDeleteConfirm(false);
  };

  return (
    <>
      {showDeleteConfirm && (
        <ConfirmDialog
          message="職務経歴書のデータを全て削除します。この操作は取り消せません。本当に削除しますか？"
          confirmLabel="削除する"
          onConfirm={handleDelete}
          onCancel={() => setShowDeleteConfirm(false)}
          confirming={deleting}
        />
      )}
      {previewUrl && <PdfPreviewModal previewUrl={previewUrl} onClose={closePreview} />}
      <form onSubmit={onSubmit}>
        <div className={shared.pageHeader}>
          <h1>職務経歴書</h1>
          <div className={shared.pageHeaderActions}>
            <button type="submit" className="primary" disabled={!canSubmit || saving}>
              {saveButtonText}
              <DirtyDot visible={dirty.any} title="未保存の変更があります" />
            </button>
            <button
              type="button"
              onClick={() => resumeId && onPreviewPdf(resumeId)}
              disabled={!resumeId || loading}
            >
              プレビュー
            </button>
            <button
              type="button"
              onClick={() =>
                resumeId &&
                onDownloadPdf(resumeId, "職務経歴書PDFをダウンロードしました。")
              }
              disabled={!resumeId || downloading || loading}
            >
              {downloading ? "ダウンロード中..." : "PDF出力"}
            </button>
            <button
              type="button"
              onClick={() => resumeId && onDownloadMarkdown(resumeId)}
              disabled={!resumeId || loading}
            >
              Markdown出力
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={!resumeId || loading}
            >
              データを削除
            </button>
          </div>
        </div>

        <div className={shared.pageBody}>
          <div className={shared.form}>
            {error && <p className={shared.error}>{error}</p>}
            {success && <p className={shared.success}>{success}</p>}

            {/* 基本情報: 氏名・職務要約 */}
            <CareerBasicInfoSection
              fullName={form.full_name}
              careerSummary={form.career_summary}
              loading={loading}
              onChange={onChangeField}
              fullNameDirty={dirty.full_name}
              careerSummaryDirty={dirty.career_summary}
            />

            {/* 職務経歴セクション */}
            {loading ? (
              <section className={shared.section}>
                <Skeleton height="20px" width="80px" borderRadius="4px" />
                <div className={shared.entry} style={{ marginTop: "0.8rem" }}>
                  <Skeleton height="120px" />
                </div>
                <div className={shared.entry}>
                  <Skeleton height="120px" />
                </div>
              </section>
            ) : (
              <CareerExperienceSection
                experiences={form.experiences}
                setForm={setForm}
                techStackOptions={techStackOptions}
                experiencesDirty={dirty.experiences}
                sectionDirty={dirty.experiencesAny}
              />
            )}

            {/* 資格セクション */}
            <CareerQualificationsSection
              qualifications={form.qualifications}
              qualificationNames={qualificationNames}
              loading={loading}
              setForm={setForm}
              qualificationsDirty={dirty.qualifications}
              sectionDirty={dirty.qualificationsAny}
            />

            {/* 自己PR */}
            <CareerSelfPrSection
              selfPr={form.self_pr}
              loading={loading}
              onChange={(v) => onChangeField("self_pr", v)}
              dirty={dirty.self_pr}
            />
          </div>
        </div>
      </form>
    </>
  );
}
