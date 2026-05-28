/**
 * Frontend 完結のメッセージ定数 (Single Source of Truth)。
 *
 * ## 役割分担
 *
 * - **API 経由のエラー**: backend `backend/app/messages.json` を正本とし、
 *   `AppErrorResponse.message` をそのまま画面表示する。本ファイルでは扱わない。
 * - **frontend 完結のメッセージ**: backend を経由しない文言（フォームのバリデーション・
 *   catch ブロックの fallback・JSX 直書きなど）は本ファイルに集約する。
 *
 * ## ルール
 *
 * - ts/tsx 内で `throw new Error("...")` `setError("...")` `toast.error("...")`
 *   などにユーザー向け日本語リテラルを直接書かない。必ず本ファイルの定数を参照する。
 * - 検知は ESLint (`no-restricted-syntax`) と `make lint-frontend-messages` で機械化されている。
 * - 詳細は `.claude/rules/frontend/messages.md` 参照。
 */

/** フォーム入力時の事前バリデーションメッセージ（payloadBuilders などで使用） */
export const VALIDATION_MESSAGES = {
  FULL_NAME_REQUIRED: "氏名を入力してください。",
  CAREER_SUMMARY_REQUIRED: "職務要約を入力してください。",
  SELF_PR_REQUIRED: "自己PRを入力してください。",
  EXPERIENCE_REQUIRED_FIELDS: "職務経歴は会社名、事業内容、開始年月を入力してください。",
  EXPERIENCE_END_DATE_REQUIRED: "職務経歴の離職年月を入力するか、在職を選択してください。",
  EXPERIENCE_DESCRIPTION_REQUIRED: "非IT企業の職務経歴は詳細を入力してください。",
  VACATION_START_DATE_REQUIRED: "休暇の開始年月を入力してください。",
  VACATION_END_DATE_REQUIRED: "休暇の終了年月を入力するか、継続中を選択してください。",
  PROJECT_START_DATE_REQUIRED: "プロジェクトの開始年月を入力してください。",
  PROJECT_END_DATE_REQUIRED: "プロジェクトの終了年月を入力するか、参画中を選択してください。",
  DATE_RANGE_INVALID: "開始日は終了日より前に設定してください。",
  QUALIFICATION_REQUIRED_FIELDS: "資格は取得日と名称を両方入力してください。",
  RESUME_PDF_REQUIRED: "PDF をアップロードしてください。",
  RESUME_PDF_SIZE_EXCEEDED: "10 MB 以下の PDF をアップロードしてください。",
} as const;

/** ネットワーク / API クライアント層の fallback メッセージ */
export const NETWORK_MESSAGES = {
  CONNECTION_FAILED: "サーバーに接続できません。ネットワーク接続を確認してください。",
  AUTH_REQUIRED: "認証が必要です。再度ログインしてください。",
  SERVER_ERROR: "サーバーエラーが発生しました。しばらくしてから再度お試しください。",
  REQUEST_FAILED: "リクエストの処理に失敗しました。",
} as const;

/** catch ブロック / toAppError fallback などで使う「失敗時の汎用文言」 */
export const FALLBACK_MESSAGES = {
  PDF_DOWNLOAD: "PDFダウンロード中に不明なエラーが発生しました。",
  MARKDOWN_DOWNLOAD: "Markdownダウンロードに失敗しました。",
  PREVIEW: "プレビューに失敗しました。",
  SAVE: "保存中に不明なエラーが発生しました。",
  DELETE: "削除中に不明なエラーが発生しました。",
  ANALYSIS: "分析に失敗しました",
  ANALYSIS_DELETE: "削除に失敗しました",
  ANALYSIS_RERUN: "再実行に失敗しました",
  BLOG_FETCH: "データの取得に失敗しました",
  BLOG_SYNC: "記事の同期に失敗しました。「同期」ボタンで再試行してください。",
  BLOG_LINK: "アカウントの連携に失敗しました",
  BLOG_SYNC_SIMPLE: "同期に失敗しました",
  BLOG_UNLINK: "アカウントの解除に失敗しました",
  BLOG_USERNAME_UPDATE: "usernameの更新に失敗しました",
  DOWNLOAD: "ダウンロードに失敗しました",
  PREVIEW_FETCH: "プレビューの取得に失敗しました",
  AUTH_CHECK: "ログイン状態の確認に失敗しました。",
  GITHUB_OAUTH_START: "GitHub OAuth の開始に失敗しました",
} as const;

/** JSX に直書きされていた UI 文言（ErrorBoundary など） */
export const UI_MESSAGES = {
  ERROR_BOUNDARY_TITLE: "予期しないエラーが発生しました",
  ERROR_BOUNDARY_BODY:
    "ページの表示中に問題が発生しました。再読み込みするか、ホームへ戻ってください。",
  GITHUB_LINK_EMPTY:
    "まだ連携データがありません。連携してアクティビティを可視化しましょう。",
} as const;

/** PDF 取り込み補助（PDF ビュー上の選択 → 流し込み）UI の文言 */
export const IMPORT_ASSIST_MESSAGES = {
  TITLE: "PDFから下書きを取り込む",
  HINT: "フォームの入力欄をクリックして選ぶ（緑枠）と、右のPDF上で選択した文字がその欄に流し込まれます。テキスト欄は続けて選択で追記できます。",
  SELECT_FILE: "PDFから取り込み",
  RESELECT_FILE: "PDFを選び直す",
  RENDERING: "PDFを表示中...",
  EMPTY: "PDFを選ぶと、ここに原本が表示されます。文字をドラッグで選択して入力欄へ流し込めます。",
  NO_TEXT:
    "このPDFから文字を選択できませんでした（スキャンPDFの可能性があります）。文字を選択できるPDFをお試しください。",
  RENDER_FAILED: "PDFの表示に失敗しました。別のファイルをお試しください。",
  NO_TARGET: "先にフォームの入力欄をクリックして、流し込み先を選んでください。",
  TAB_FALLBACK: "PDF",
  ZOOM_IN: "拡大",
  ZOOM_OUT: "縮小",
} as const;

/**
 * 非同期バックグラウンドタスクのローディング UI 文言（AsyncTaskLoading で使用）。
 * PDF アップロード / GitHub 連携 で共通の補足メッセージと、
 * 機能ごとの処理内容ラベルを集約する。
 */
export const LOADING_MESSAGES = {
  /** 補足: 画面遷移してもタスクが継続する旨 */
  BACKGROUND_CONTINUES: "他の画面に移動しても処理は継続されます",
  /** 補足: 処理に時間がかかる旨 */
  TAKES_TIME: "この処理には時間がかかります",
  /** GitHub 連携中ラベル */
  GITHUB_LINK: "GitHubプロフィールを取得中...",
} as const;

/** ダウンロード失敗時のメッセージにファイル名を付与する。 */
export function downloadFailureMessage(filename: string): string {
  return `${FALLBACK_MESSAGES.DOWNLOAD}: ${filename}`;
}
