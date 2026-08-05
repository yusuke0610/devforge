import { CSSProperties, useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useCareerFormModals } from "../../hooks/career/useCareerFormModals";

import {
  createCareerResume,
  deleteCareerResume,
  getLatestCareerResume,
  updateCareerResume,
} from "../../api";
import {
  AUTH_PROMPT_MESSAGES,
  RESUME_DRAFT_MESSAGES,
  SUCCESS_MESSAGES,
  UI_MESSAGES,
} from "../../constants/messages";
import type { ResumeDraftResultResponse } from "../../api/types";
import { createInitialCareerForm, mapCareerResumeToForm } from "../../formMappers";
import { useCareerDirty } from "../../hooks/career/useCareerDirty";
import { useCareerDraftRestore } from "../../hooks/career/useCareerDraftRestore";
import { useImportPanelLayout } from "../../hooks/career/useImportPanelLayout";
import { useResumeImportAssist } from "../../hooks/career/useResumeImportAssist";
import { useDocumentForm } from "../../hooks/useDocumentForm";
import { clearCareerDraft, loadCareerDraft, saveCareerDraft } from "../../utils/careerDraft";
import {
  appendResumeDraftProjects,
  hasCareerFormContent,
  type DraftInjectionTarget,
} from "../../utils/resumeImport";
import { buildCareerPayload } from "../../payloadBuilders";
import { useCareerFormValidationFocus } from "../../hooks/career/useCareerFormValidationFocus";
import { useQualifications, useTechnologyStacks } from "../../hooks/useMasterData";
import { useCareerExportActions } from "../../hooks/career/useCareerExportActions";
import { useMessageToast, useToast } from "../ui/toast";
import { AgentChatWidget } from "./AgentChatWidget";
import { ResumeImportPanel } from "./ResumeImportPanel";
import shared from "../../styles/shared.module.css";
import { ConfirmDialog } from "../ConfirmDialog";
import { useLoginPrompt } from "../auth/loginPromptContext";
import { MarkdownFieldModal } from "./MarkdownFieldModal";
import { Skeleton } from "../ui/Skeleton";
import { PdfPreviewModal } from "./PdfPreviewModal";
import { ResumeDraftInjectDialog } from "./ResumeDraftInjectDialog";
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
    editingField,
    setEditingField,
    handleDelete,
  } = useCareerFormModals({ deleteDoc });

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

  // PDF 自動入力の導線は「保存済み経歴書が無く、ロード完了済みで、フォームが空」のときだけ出す
  // （ADR-0024 / #528）。認証ユーザは loadLatest 完了前に空フォームが見えるため、!loading &&
  // !resumeId でガードして既存経歴書との競合（インポートがロード結果で上書きされる/既存に
  // 適用される）を防ぐ。入力・抽出後は内容が入るため自然に消える。
  const showImportPanel = !loading && !resumeId && !hasCareerFormContent(form);

  // GitHub 連携画面から「フォームに反映」で渡されたドラフト payload（ADR-0025 / #525）。
  const location = useLocation();
  const navigate = useNavigate();
  const { showSuccess } = useToast();
  const draftPayload = (location.state as { resumeDraftPayload?: ResumeDraftResultResponse } | null)
    ?.resumeDraftPayload;
  const [pendingDraft, setPendingDraft] = useState<ResumeDraftResultResponse | null>(null);
  const appliedDraftRef = useRef(false);

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
    save,
    requestLogin,
    // ゲスト入力はログイン遷移の直前に同期退避する（effect の未反映で最後の入力を失わないため）。
    persistDraft: saveCareerDraft,
    openMarkdownField: setEditingField,
  });

  // ドラフトの案件を既存の職歴へ追加する（置換しない・DB 非更新 / ADR-0026 決定 5）。
  // setFormAndClearFocus が定義済みの位置で宣言する必要があるためここに置く。
  const appendDraftProjects = useCallback(
    (payload: ResumeDraftResultResponse, target: DraftInjectionTarget | null) => {
      setFormAndClearFocus((prev) => appendResumeDraftProjects(prev, payload, target));
      showSuccess(RESUME_DRAFT_MESSAGES.APPLIED_TOAST);
    },
    [setFormAndClearFocus, showSuccess],
  );

  // 職務要約・自己PR は上書きになるため、候補としてユーザーが個別に反映する
  const applyDraftCandidate = useCallback(
    (field: "career_summary" | "self_pr", value: string) => {
      setFormAndClearFocus((prev) => ({ ...prev, [field]: value }));
      showSuccess(RESUME_DRAFT_MESSAGES.CANDIDATE_APPLIED_TOAST);
    },
    [setFormAndClearFocus, showSuccess],
  );

  useEffect(() => {
    // loadLatest 完了前は待つ（既存経歴書との競合防止 / #528 と同じ論点）。1 度だけ開く。
    if (!draftPayload || loading || appliedDraftRef.current) return;
    appliedDraftRef.current = true;
    // router state を消す（リロード・再レンダリングでの再表示を防ぐ）
    navigate(location.pathname, { replace: true, state: null });
    // 追加先はユーザーが選ぶ（機械が推測しない）。上書き確認は不要になった（追加のみのため）
    setPendingDraft(draftPayload);
  }, [draftPayload, loading, navigate, location.pathname]);

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
      {previewUrl && <PdfPreviewModal previewUrl={previewUrl} onClose={closePreview} />}
      {/* ドラフトの案件追加（追加先の指定 + 職務要約・自己PR の候補提示 / ADR-0026 決定 5） */}
      {pendingDraft && (
        <ResumeDraftInjectDialog
          form={form}
          payload={pendingDraft}
          onAppend={(target) => {
            appendDraftProjects(pendingDraft, target);
            setPendingDraft(null);
          }}
          onApplyCandidate={applyDraftCandidate}
          onClose={() => setPendingDraft(null)}
        />
      )}
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

                {/* 空フォームの新規ユーザ向け: 手持ち PDF から自動入力（ADR-0024 / #528） */}
                {showImportPanel && (
                  <ResumeImportPanel
                    form={form}
                    onApply={setFormAndClearFocus}
                    isAuthenticated={isAuthenticated}
                    requestLogin={requestLogin}
                  />
                )}

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
