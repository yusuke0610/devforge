import { CSSProperties, FormEvent, useMemo, useRef, useState } from "react";

import {
  createCareerResume,
  deleteCareerResume,
  downloadCareerResumeMarkdown,
  downloadCareerResumePdf,
  getCareerResumePdfBlobUrl,
  getLatestCareerResume,
  updateCareerResume,
} from "../../api";
import { UI_MESSAGES } from "../../constants/messages";
import { createInitialCareerForm, mapCareerResumeToForm } from "../../formMappers";
import { useCareerDirty } from "../../hooks/career/useCareerDirty";
import { useImportPanelLayout } from "../../hooks/career/useImportPanelLayout";
import { useResumeDiffPreview } from "../../hooks/career/useResumeDiffPreview";
import { useResumeImportAssist } from "../../hooks/career/useResumeImportAssist";
import { useDocumentForm } from "../../hooks/useDocumentForm";
import { buildCareerPayload } from "../../payloadBuilders";
import { buildCareerChanges } from "../../utils/careerDiff";
import type { CareerTextFieldKey } from "../../formTypes";
import { useQualifications, useTechnologyStacks } from "../../hooks/useMasterData";
import { usePdfActions } from "../../hooks/usePdfActions";
import shared from "../../styles/shared.module.css";
import { ConfirmDialog } from "../ConfirmDialog";
import { CareerDiffModal } from "./CareerDiffModal";
import { Skeleton } from "../ui/Skeleton";
import { PdfPreviewModal } from "./PdfPreviewModal";
import { ResumeSourceTracePanel } from "./ResumeSourceTracePanel";
import layout from "./CareerResumeForm.module.css";
import { CareerBasicInfoSection } from "./sections/CareerBasicInfoSection";
import { CareerExperienceSection } from "./sections/CareerExperienceSection";
import { CareerQualificationsSection } from "./sections/CareerQualificationsSection";
import { CareerSelfPrSection } from "./sections/CareerSelfPrSection";

export function CareerResumeForm() {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  // 保存時の変更点確認ダイアログの表示状態。
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);
  // PDF 原本ビュー（右カラム）の折りたたみ状態。折りたたむと入力フォームが全幅に広がる。
  const [pdfCollapsed, setPdfCollapsed] = useState(false);
  const assist = useResumeImportAssist();
  const splitRef = useRef<HTMLDivElement>(null);
  const { width: pdfWidth, startResize } = useImportPanelLayout(splitRef);
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

  /**
   * baseline（保存済み）と form（編集中）の変更点リスト。左右 diff モーダルのサイドバーと
   * ハイライト突合に使う。baseline が未ロード（null）のときは form 同士を比較して変更なし扱い。
   */
  const changes = useMemo(
    () => buildCareerChanges(form, baseline ?? form),
    [form, baseline],
  );

  /** 左右 diff モーダル用の整形 HTML プレビュー（保存済み / 編集中）。開いている間だけ取得する。 */
  const preview = useResumeDiffPreview(form, baseline, showSaveConfirm);

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
  const error = pdfError ?? formError ?? null;
  const success = pdfSuccess ?? formSuccess;

  /** Skeleton 表示・入力ロックの統合フラグ */
  const formLocked = loading;

  /** フォームデータ・技術スタック・資格の3つが揃った時に送信可能 */
  const canSubmit = !loading && !techLoading && !qualLoading;

  const onChangeField = (key: CareerTextFieldKey, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    // 変更が無ければ確認を挟まずそのまま保存。変更があれば確認ダイアログを開く。
    if (changes.length === 0) {
      void save();
      return;
    }
    setShowSaveConfirm(true);
  };

  /** 確認ダイアログで「この内容で保存」を押したときの確定処理。 */
  const handleConfirmSave = async () => {
    await save();
    setShowSaveConfirm(false);
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
      {showSaveConfirm && (
        <CareerDiffModal
          changes={changes}
          baselineHtml={preview.baselineHtml}
          editedHtml={preview.editedHtml}
          css={preview.css}
          loading={preview.loading}
          error={preview.error}
          saving={saving}
          onConfirm={handleConfirmSave}
          onCancel={() => setShowSaveConfirm(false)}
          onRollback={(change) => setForm((prev) => change.rollback(prev))}
        />
      )}
      {previewUrl && <PdfPreviewModal previewUrl={previewUrl} onClose={closePreview} />}
      <form onSubmit={onSubmit}>
        <div className={shared.pageHeader}>
          <h1>職務経歴書</h1>
          <div className={shared.pageHeaderActions}>
            {/* ファイル取り込みは右カラムの原本ビュー（ドラッグ&ドロップ / クリック）に集約。 */}
            <button type="submit" className="primary" disabled={!canSubmit || saving}>
              {saveButtonText}
            </button>
            <button
              type="button"
              onClick={() => resumeId && onPreviewPdf(resumeId)}
              disabled={!resumeId || formLocked}
            >
              プレビュー
            </button>
            <button
              type="button"
              onClick={() =>
                resumeId && onDownloadPdf(resumeId, "職務経歴書PDFをダウンロードしました。")
              }
              disabled={!resumeId || downloading || formLocked}
            >
              {downloading ? "ダウンロード中..." : "PDF出力"}
            </button>
            <button
              type="button"
              onClick={() => resumeId && onDownloadMarkdown(resumeId)}
              disabled={!resumeId || formLocked}
            >
              Markdown出力
            </button>
            <button
              type="button"
              className="danger"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={!resumeId || formLocked}
            >
              データを削除
            </button>
          </div>
        </div>

        <div className={shared.pageBody}>
          {/* 左=入力フォーム / 右=PDF 原本ビュー。スプリッターで左右リサイズする。
              splitWrap はコンテナクエリの基準（= split に割り当てられる実幅）。
              横幅が足りない時は split を縦積みに切り替える。PDF カラム幅は CSS 変数で渡し、
              縦積み時は CSS 側で全幅に上書きする（inline style だと上書きできないため変数経由）。 */}
          <div className={layout.splitWrap}>
            <div
              ref={splitRef}
              className={layout.split}
              style={{ "--pdf-col-width": `${pdfWidth}px` } as CSSProperties}
            >
              {/* 左: 入力フォーム（選択中フィールドは緑枠 = import-assign-form の :focus CSS） */}
              <div className={`${shared.form} import-assign-form ${layout.formCol}`}>
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
                    assist={assist}
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

              {/* 中央: ドラッグでカラム幅を変えるスプリッター（折りたたみ時は非表示）。 */}
              {!pdfCollapsed && (
                <div
                  className={layout.splitter}
                  role="separator"
                  aria-orientation="vertical"
                  onMouseDown={startResize}
                />
              )}

              {/* 右: 原本ビュー（独立スクロール）。文字を選択して入力欄へ流し込む。
                幅は CSS 変数 --pdf-col-width を CSS 側で参照（縦積み時は全幅へ上書き）。
                折りたたみ時は細いレールになり、トグルだけを表示する。 */}
              <aside className={`${layout.pdfCol} ${pdfCollapsed ? layout.pdfColCollapsed : ""}`}>
                <button
                  type="button"
                  className={layout.pdfToggle}
                  onClick={() => setPdfCollapsed((v) => !v)}
                  aria-label={
                    pdfCollapsed ? UI_MESSAGES.SOURCE_PANEL_EXPAND : UI_MESSAGES.SOURCE_PANEL_COLLAPSE
                  }
                  aria-expanded={!pdfCollapsed}
                >
                  {pdfCollapsed ? "«" : "»"}
                </button>
                {/* 折りたたみ中でも取り込み補助のエラー（サイズ超過・パース失敗）は隠さない。
                    クリックでパネルを展開し、全文を ResumeSourceTracePanel で表示できるようにする。 */}
                {pdfCollapsed && assist.error && (
                  <button
                    type="button"
                    className={layout.collapsedError}
                    onClick={() => setPdfCollapsed(false)}
                    title={assist.error}
                    aria-label={UI_MESSAGES.SOURCE_PANEL_EXPAND}
                  >
                    !
                  </button>
                )}
                {!pdfCollapsed && <ResumeSourceTracePanel assist={assist} />}
              </aside>
            </div>
          </div>
        </div>
      </form>
    </>
  );
}
