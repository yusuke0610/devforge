import { CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useCareerFormModals } from "../../hooks/career/useCareerFormModals";

import {
  createCareerResume,
  deleteCareerResume,
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
import { buildCareerPayload } from "../../payloadBuilders";
import { buildCareerChanges } from "../../utils/careerDiff";
import { useCareerFormValidationFocus } from "../../hooks/career/useCareerFormValidationFocus";
import { useQualifications, useTechnologyStacks } from "../../hooks/useMasterData";
import { useCareerExportActions } from "../../hooks/career/useCareerExportActions";
import { useMessageToast } from "../ui/toast";
import { AgentChatWidget } from "./AgentChatWidget";
import shared from "../../styles/shared.module.css";
import { ConfirmDialog } from "../ConfirmDialog";
import { useLoginPrompt } from "../auth/loginPromptContext";
import { CareerDiffModal } from "./CareerDiffModal";
import { MarkdownFieldModal } from "./MarkdownFieldModal";
import { Skeleton } from "../ui/Skeleton";
import { PdfPreviewModal } from "./PdfPreviewModal";
import { ResumeSourceTracePanel } from "./ResumeSourceTracePanel";
import layout from "./CareerResumeForm.module.css";
import { CareerFormToolbar } from "./sections/CareerFormToolbar";
import { CareerBasicInfoSection } from "./sections/CareerBasicInfoSection";
import { CareerExperienceSection } from "./sections/CareerExperienceSection";
import { CareerQualificationsSection } from "./sections/CareerQualificationsSection";
import { CareerSelfPrSection } from "./sections/CareerSelfPrSection";

export function CareerResumeForm({ isAuthenticated }: { isAuthenticated: boolean }) {
  // 未ログインで要ログイン機能を使おうとしたときに開く共通モーダル。
  const requestLogin = useLoginPrompt();
  // PDF 原本ビュー（右カラム）の折りたたみ状態。折りたたむと入力フォームが全幅に広がる。
  const [pdfCollapsed, setPdfCollapsed] = useState(false);
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

  const {
    showDeleteConfirm,
    setShowDeleteConfirm,
    showSaveConfirm,
    setShowSaveConfirm,
    editingField,
    setEditingField,
    handleDelete,
    handleConfirmSave,
  } = useCareerFormModals({ save, deleteDoc });

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

  /** Skeleton 表示・入力ロックの統合フラグ */
  const formLocked = loading;

  const {
    downloading,
    previewUrl,
    closePreview,
    handlePreview,
    handleDownloadPdf,
    handleDownloadMarkdown,
    exportDisabled,
    error: pdfError,
    success: pdfSuccess,
  } = useCareerExportActions({
    isAuthenticated,
    resumeId: resumeId ?? null,
    formLocked,
    requestLogin,
  });

  useMessageToast(formSuccess, "success");
  useMessageToast(formError, "error");
  useMessageToast(pdfSuccess, "success");
  useMessageToast(pdfError, "error");
  // ログイン後のドラフト復元（既存経歴書あり）を通知する情報トースト。
  useMessageToast(restoreMessage, "success");

  /** フォームデータ・技術スタック・資格の3つが揃った時に送信可能 */
  const canSubmit = !loading && !techLoading && !qualLoading;

  // バリデーション結果の画面反映（メッセージ・フォーカス強調・モーダル自動展開・送信分岐）。
  const {
    validationError,
    focusLocator,
    focusNonce,
    setFormAndClearFocus,
    onChangeField,
    onSubmit,
  } = useCareerFormValidationFocus({
    form,
    setForm,
    isAuthenticated,
    changeCount: changes.length,
    save,
    openSaveConfirm: () => setShowSaveConfirm(true),
    requestLogin,
    // ゲスト入力はログイン遷移の直前に同期退避する（effect の未反映で最後の入力を失わないため）。
    persistDraft: saveCareerDraft,
    openMarkdownField: setEditingField,
  });

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
      {/* AI アシスタント（ADR-0010）。operations はフォーム state にのみ反映され、保存は既存の保存ボタンで行う */}
      <AgentChatWidget
        form={form}
        onApply={setFormAndClearFocus}
        isAuthenticated={isAuthenticated}
        requestLogin={requestLogin}
      />
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
        <CareerFormToolbar
          saveButtonText={saveButtonText}
          canSubmit={canSubmit}
          saving={saving}
          exportDisabled={exportDisabled}
          downloading={downloading}
          deleteDisabled={!resumeId || formLocked}
          onPreview={handlePreview}
          onDownloadPdf={handleDownloadPdf}
          onDownloadMarkdown={handleDownloadMarkdown}
          onDelete={() => setShowDeleteConfirm(true)}
        />

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

                {/* 基本情報: 氏名・連絡先・職務要約 */}
                <CareerBasicInfoSection
                  fullName={form.full_name}
                  email={form.email}
                  githubUrl={form.github_url}
                  careerSummary={form.career_summary}
                  loading={loading}
                  onChange={onChangeField}
                  onEditCareerSummary={() => setEditingField("career_summary")}
                  fullNameDirty={dirty.full_name}
                  emailDirty={dirty.email}
                  githubUrlDirty={dirty.github_url}
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
