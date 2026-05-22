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
  RESUME_EXTRACT: "抽出結果の取得に失敗しました。",
  BLOG_FETCH: "データの取得に失敗しました",
  BLOG_SYNC: "記事の同期に失敗しました。「同期」ボタンで再試行してください。",
  BLOG_LINK: "アカウントの連携に失敗しました",
  BLOG_SYNC_SIMPLE: "同期に失敗しました",
  BLOG_UNLINK: "アカウントの解除に失敗しました",
  BLOG_USERNAME_UPDATE: "usernameの更新に失敗しました",
  BLOG_SUMMARY_FAILED: "AI分析に失敗しました",
  BLOG_SUMMARY_UNAVAILABLE: "AI分析サーバーに接続できません",
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
} as const;

/** 開発者向け（通常はユーザーに表示されない）の内部エラーメッセージ */
export const INTERNAL_MESSAGES = {
  RESUME_IMPORT_NO_ID: "import_id が未設定です",
} as const;

/** ダウンロード失敗時のメッセージにファイル名を付与する。 */
export function downloadFailureMessage(filename: string): string {
  return `${FALLBACK_MESSAGES.DOWNLOAD}: ${filename}`;
}
