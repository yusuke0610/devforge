import { CSSProperties, FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";

import {
  createCareerResume,
  deleteCareerResume,
  downloadCareerResumeMarkdown,
  downloadCareerResumePdf,
  getCareerResumePdfBlobUrl,
  getLatestCareerResume,
  updateCareerResume,
} from "../../api";
import { AUTH_PROMPT_MESSAGES, SUCCESS_MESSAGES, UI_MESSAGES } from "../../constants/messages";
import { createInitialCareerForm, mapCareerResumeToForm } from "../../formMappers";
import { useCareerDirty } from "../../hooks/career/useCareerDirty";
import { useCareerDraftRestore } from "../../hooks/career/useCareerDraftRestore";
import { useImportPanelLayout } from "../../hooks/career/useImportPanelLayout";
import { useResumeDiffPreview } from "../../hooks/career/useResumeDiffPreview";
import { useResumeImportAssist } from "../../hooks/career/useResumeImportAssist";
import { useDocumentForm } from "../../hooks/useDocumentForm";
import { clearCareerDraft, loadCareerDraft, saveCareerDraft } from "../../utils/careerDraft";
import { buildCareerPayload, validateCareerForm } from "../../payloadBuilders";
import type { CareerFieldLocator, CareerFormState } from "../../payloadBuilders";
import { buildCareerChanges } from "../../utils/careerDiff";
import type { CareerTextFieldKey } from "../../formTypes";
import { useQualifications, useTechnologyStacks } from "../../hooks/useMasterData";
import { usePdfActions } from "../../hooks/usePdfActions";
import { useMessageToast } from "../ui/toast";
import shared from "../../styles/shared.module.css";
import { ConfirmDialog } from "../ConfirmDialog";
import { useLoginPrompt } from "../auth/loginPromptContext";
import { CareerDiffModal } from "./CareerDiffModal";
import { MarkdownFieldModal } from "./MarkdownFieldModal";
import { Skeleton } from "../ui/Skeleton";
import { SaveIcon } from "../icons/SaveIcon";
import { EyeIcon } from "../icons/EyeIcon";
import { TrashIcon } from "../icons/TrashIcon";
import { PdfDownloadIcon } from "../icons/PdfDownloadIcon";
import { MarkdownDownloadIcon } from "../icons/MarkdownDownloadIcon";
import { PdfPreviewModal } from "./PdfPreviewModal";
import { ResumeSourceTracePanel } from "./ResumeSourceTracePanel";
import layout from "./CareerResumeForm.module.css";
import { CareerBasicInfoSection } from "./sections/CareerBasicInfoSection";
import { CareerExperienceSection } from "./sections/CareerExperienceSection";
import { CareerQualificationsSection } from "./sections/CareerQualificationsSection";
import { CareerSelfPrSection } from "./sections/CareerSelfPrSection";

export function CareerResumeForm({ isAuthenticated }: { isAuthenticated: boolean }) {
  // 未ログインで要ログイン機能を使おうとしたときに開く共通モーダル。
  const requestLogin = useLoginPrompt();
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  // 保存時の変更点確認ダイアログの表示状態。
  const [showSaveConfirm, setShowSaveConfirm] = useState(false);
  // PDF 原本ビュー（右カラム）の折りたたみ状態。折りたたむと入力フォームが全幅に広がる。
  const [pdfCollapsed, setPdfCollapsed] = useState(false);
  // 自己PR / 職務要約の入力モーダルの対象フィールド（null で閉じている）。
  const [editingField, setEditingField] = useState<"career_summary" | "self_pr" | null>(null);
  const assist = useResumeImportAssist();
  const splitRef = useRef<HTMLDivElement>(null);
  const { width: pdfWidth, startResize } = useImportPanelLayout(splitRef);

  /**
   * 初期フォーム。未ログインのお試し入力では、退避ドラフトがあればそれを初期値にする
   * （リロードやログイン往復後も入力を失わない。ドラフトは下の effect で常に最新化する）。
   * 認証済みでは空フォーム（サーバ最新は useDocumentForm の loadLatest が反映する）。
   */
  const createInitialForm = useCallback(
    () => (isAuthenticated ? createInitialCareerForm() : loadCareerDraft() ?? createInitialCareerForm()),
    [isAuthenticated],
  );

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
    createInitialForm,
    loadLatest: getLatestCareerResume,
    createDocument: createCareerResume,
    updateDocument: updateCareerResume,
    deleteDocument: deleteCareerResume,
    buildPayload: buildCareerPayload,
    mapResponseToForm: mapCareerResumeToForm,
    successMessage: SUCCESS_MESSAGES.CAREER_SAVED,
    cacheKey: "career",
    // 未ログインのお試し入力では loadLatest を行わず空フォームで起動する（401 を無駄打ちしない）。
    skipLoad: !isAuthenticated,
  });

  // ログイン後（往復から復帰）に退避ドラフトを復元する情報トースト用メッセージ。
  const [restoreMessage, setRestoreMessage] = useState<string | null>(null);

  // 未ログイン入力 → ログイン往復してきたユーザーの退避ドラフトをフォームへ橋渡しする。
  useCareerDraftRestore({
    isAuthenticated,
    loading,
    documentId: resumeId,
    setForm,
    save,
    notifyRestored: () => setRestoreMessage(AUTH_PROMPT_MESSAGES.DRAFT_RESTORED),
  });

  /**
   * 未ログイン時は入力内容を常に sessionStorage に退避し続ける。
   * これによりプレビュー/ダウンロード/連携メニューなど任意のログイン導線を踏んでも
   * 入力が失われず、ログイン往復後に復元できる。氏名が空のうちは意味のあるドラフトでないため退避しない
   * （空ドラフトでログイン後に自動保存が空振りするのを防ぐ）。
   */
  useEffect(() => {
    if (isAuthenticated) return;
    if (form.full_name.trim()) {
      saveCareerDraft(form);
    } else {
      clearCareerDraft();
    }
  }, [isAuthenticated, form]);

  /**
   * 保存前バリデーション（項目バリデーション）のメッセージ。
   * 保存/削除/PDF などの非同期処理の成否はトーストで通知するが、
   * 入力エラーは該当フィールドのフォーカス・赤枠とセットでフォーム内にインライン表示する。
   */
  const [validationError, setValidationError] = useState<string | null>(null);

  const { items: techStackOptions, loading: techLoading } = useTechnologyStacks();
  const { items: qualificationOptions, loading: qualLoading } = useQualifications();
  const qualificationNames = qualificationOptions.map((item) => item.name);

  /** 未保存マーク（🔴）の表示判定に使う dirty マップ */
  const dirty = useCareerDirty(form, baseline);

  /**
   * baseline（保存済み）と form（編集中）の変更点リスト。左右 diff モーダルのサイドバーと
   * ハイライト突合に使う。
   *
   * baseline が未ロード（null = 新規作成の初回保存）のときは「空フォーム」を基準にする。
   * これにより初回保存でも全項目が「追加」として変更点に立ち、確認ダイアログが開く
   * （= 初回も校正を見せる）。既存データで差分が無い場合は changes が空のまま直接保存される。
   */
  const changes = useMemo(
    () => buildCareerChanges(form, baseline ?? createInitialCareerForm()),
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

  useMessageToast(formSuccess, "success");
  useMessageToast(formError, "error");
  useMessageToast(pdfSuccess, "success");
  useMessageToast(pdfError, "error");
  // ログイン後のドラフト復元（既存経歴書あり）を通知する情報トースト。
  useMessageToast(restoreMessage, "success");

  /** Skeleton 表示・入力ロックの統合フラグ */
  const formLocked = loading;

  /** フォームデータ・技術スタック・資格の3つが揃った時に送信可能 */
  const canSubmit = !loading && !techLoading && !qualLoading;

  /**
   * バリデーション失敗フィールドの位置と nonce。保存時にセットし、
   * 該当入力へのフォーカス・赤枠表示・折りたたみ自動展開に使う。
   * nonce は「同じフィールドで再度保存した時」も折りたたみ展開 effect を再発火させるための鍵。
   */
  const [focusTarget, setFocusTarget] = useState<{
    locator: CareerFieldLocator;
    nonce: number;
  } | null>(null);
  const focusNonceRef = useRef(0);

  /** 編集が入ったらフォーカス強調を解除する（赤枠を消す）setForm ラッパー。 */
  const setFormAndClearFocus = useCallback<Dispatch<SetStateAction<CareerFormState>>>(
    (action) => {
      setFocusTarget(null);
      setValidationError(null);
      setForm(action);
    },
    [setForm],
  );

  const onChangeField = (key: CareerTextFieldKey, value: string) => {
    setFocusTarget(null);
    setValidationError(null);
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  /** バリデーション失敗を画面へ反映する（メッセージ・フォーカス・モーダル自動展開）。 */
  const applyValidationError = (validation: NonNullable<ReturnType<typeof validateCareerForm>>) => {
    setValidationError(validation.message);
    focusNonceRef.current += 1;
    setFocusTarget({ locator: validation.locator, nonce: focusNonceRef.current });
    // 自己PR / 職務要約はモーダルへ逃がしているため、該当フィールドの失敗時はモーダルを自動で開く
    // （隠れた textarea には直接フォーカスできないため）。
    if (
      validation.locator.kind === "career_summary" ||
      validation.locator.kind === "self_pr"
    ) {
      setEditingField(validation.locator.kind);
    }
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();

    // 未ログインのお試し入力: 全項目の入力完了は求めず（カジュアルな体験を優先）、
    // 氏名だけ確認して（空の経歴書でログインさせない）ドラフトを退避し、ログインを促す。
    // 残りの項目検証はログイン後の実保存時にサーバ側で行う。
    if (!isAuthenticated) {
      if (!form.full_name.trim()) {
        const validation = validateCareerForm(form);
        if (validation) applyValidationError(validation);
        return;
      }
      setValidationError(null);
      setFocusTarget(null);
      // 入力内容は effect で sessionStorage に退避済み。ログインを促す。
      requestLogin();
      return;
    }

    // 保存前にフォーム全体を検証し、最初のエラーフィールドへフォーカスする。
    const validation = validateCareerForm(form);
    if (validation) {
      applyValidationError(validation);
      return;
    }
    setValidationError(null);
    setFocusTarget(null);
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

  const focusLocator = focusTarget?.locator ?? null;
  const focusNonce = focusTarget?.nonce ?? 0;

  const handleDelete = async () => {
    await deleteDoc();
    setShowDeleteConfirm(false);
  };

  /**
   * 要ログイン機能（プレビュー / PDF / Markdown 出力）のハンドラ。
   * 未ログインならログイン促進モーダルを開き、ログイン済みなら本来の処理を行う。
   * 入力中ドラフトは effect で sessionStorage に退避済みのため、ログイン往復後も失われない。
   */
  const handlePreview = () => {
    if (!isAuthenticated) return requestLogin();
    if (resumeId) onPreviewPdf(resumeId);
  };
  const handleDownloadPdf = () => {
    if (!isAuthenticated) return requestLogin();
    if (resumeId) onDownloadPdf(resumeId, SUCCESS_MESSAGES.CAREER_PDF_DOWNLOADED);
  };
  const handleDownloadMarkdown = () => {
    if (!isAuthenticated) return requestLogin();
    if (resumeId) onDownloadMarkdown(resumeId);
  };
  // 未ログインでは要ログイン機能ボタンを活性にしてログイン導線にする。
  // ログイン済みでは保存済み（resumeId あり）まで非活性。
  const exportDisabled = formLocked || (isAuthenticated && !resumeId);

  return (
    <>
      {showDeleteConfirm && (
        <ConfirmDialog
          message={UI_MESSAGES.RESUME_DELETE_CONFIRM}
          confirmLabel={UI_MESSAGES.RESUME_DELETE_CONFIRM_LABEL}
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
      {editingField && (
        <MarkdownFieldModal
          title={
            editingField === "self_pr"
              ? UI_MESSAGES.FIELD_SELF_PR
              : UI_MESSAGES.FIELD_CAREER_SUMMARY
          }
          value={form[editingField]}
          onChange={(v) => onChangeField(editingField, v)}
          onClose={() => setEditingField(null)}
          assist={assist}
          invalid={focusLocator?.kind === editingField}
        />
      )}
      {/* noValidate: 必須チェックはブラウザ標準ではなく validateCareerForm に一本化する。
          標準の required バブルが先に発火すると、該当フィールドへの独自フォーカス・赤枠・
          日本語メッセージが出せず挙動が不統一になるため抑止する。 */}
      <form onSubmit={onSubmit} noValidate>
        <div className={shared.pageHeader}>
          <h1>職務経歴書</h1>
          <div className={shared.pageHeaderActions}>
            {/* ファイル取り込みは右カラムの原本ビュー（ドラッグ&ドロップ / クリック）に集約。 */}
            <button
              type="submit"
              className={`primary ${layout.iconButton}`}
              disabled={!canSubmit || saving}
              aria-label={saveButtonText}
              title={saveButtonText}
            >
              {saving ? (
                <span className={layout.buttonSpinner} aria-hidden="true" />
              ) : (
                <SaveIcon className={layout.headerIcon} />
              )}
            </button>
            <button
              type="button"
              className={layout.iconButton}
              onClick={handlePreview}
              disabled={exportDisabled}
              aria-label={UI_MESSAGES.RESUME_PREVIEW}
              title={UI_MESSAGES.RESUME_PREVIEW}
            >
              <EyeIcon className={layout.headerIcon} />
            </button>
            <button
              type="button"
              className={layout.iconButton}
              onClick={handleDownloadPdf}
              disabled={exportDisabled || downloading}
              aria-label={UI_MESSAGES.RESUME_EXPORT_PDF}
              title={UI_MESSAGES.RESUME_EXPORT_PDF}
            >
              {downloading ? (
                <span className={layout.buttonSpinner} aria-hidden="true" />
              ) : (
                <PdfDownloadIcon className={layout.headerIcon} />
              )}
            </button>
            <button
              type="button"
              className={layout.iconButton}
              onClick={handleDownloadMarkdown}
              disabled={exportDisabled}
              aria-label={UI_MESSAGES.RESUME_EXPORT_MARKDOWN}
              title={UI_MESSAGES.RESUME_EXPORT_MARKDOWN}
            >
              <MarkdownDownloadIcon className={layout.headerIcon} />
            </button>
            <button
              type="button"
              className={`danger ${layout.iconButton}`}
              onClick={() => setShowDeleteConfirm(true)}
              disabled={!resumeId || formLocked}
              aria-label={UI_MESSAGES.RESUME_DELETE_ALL}
              title={UI_MESSAGES.RESUME_DELETE_ALL}
            >
              <TrashIcon className={layout.headerIcon} />
            </button>
          </div>
        </div>

        <div className={shared.pageBody}>
          <div className={layout.splitWrap}>
            <div
              ref={splitRef}
              className={layout.split}
              style={{ "--pdf-col-width": `${pdfWidth}px` } as CSSProperties}
            >
              {/* 左: 入力フォーム（選択中フィールドは緑枠 = import-assign-form の :focus CSS） */}
              <div className={`${shared.form} import-assign-form ${layout.formCol}`}>
                {validationError && <p className={shared.error}>{validationError}</p>}

                {/* 基本情報: 氏名・職務要約 */}
                <CareerBasicInfoSection
                  fullName={form.full_name}
                  careerSummary={form.career_summary}
                  loading={loading}
                  onChange={onChangeField}
                  onEditCareerSummary={() => setEditingField("career_summary")}
                  fullNameDirty={dirty.full_name}
                  careerSummaryDirty={dirty.career_summary}
                  focusLocator={focusLocator}
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
                    setForm={setFormAndClearFocus}
                    techStackOptions={techStackOptions}
                    experiencesDirty={dirty.experiences}
                    sectionDirty={dirty.experiencesAny}
                    assist={assist}
                    focusLocator={focusLocator}
                    focusNonce={focusNonce}
                  />
                )}

                {/* 資格セクション */}
                <CareerQualificationsSection
                  qualifications={form.qualifications}
                  qualificationNames={qualificationNames}
                  loading={loading}
                  setForm={setFormAndClearFocus}
                  qualificationsDirty={dirty.qualifications}
                  sectionDirty={dirty.qualificationsAny}
                  focusLocator={focusLocator}
                  focusNonce={focusNonce}
                />

                {/* 自己PR */}
                <CareerSelfPrSection
                  selfPr={form.self_pr}
                  loading={loading}
                  onEdit={() => setEditingField("self_pr")}
                  dirty={dirty.self_pr}
                  focusLocator={focusLocator}
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
                    pdfCollapsed
                      ? UI_MESSAGES.SOURCE_PANEL_EXPAND
                      : UI_MESSAGES.SOURCE_PANEL_COLLAPSE
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
