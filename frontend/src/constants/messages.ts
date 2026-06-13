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
  EMAIL_REQUIRED: "メールアドレスを入力してください。",
  EMAIL_INVALID: "メールアドレスの形式が正しくありません。",
  GITHUB_URL_INVALID: "GitHub の URL は https://github.com/ で始まる形式で入力してください。",
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
  GITHUB_LINK: "連携に失敗しました",
  AGENT_CHAT: "AI への送信に失敗しました",
  CREDIT_BALANCE: "クレジット残高の取得に失敗しました",
} as const;

/**
 * 操作成功時にユーザーへ表示する文言（frontend 完結）。
 * backend を経由しない「保存しました」「連携しました」等の success トーストに使う。
 * 動的に件数を埋め込むものは下部の関数（blogSyncSuccessMessage 等）を使う。
 */
export const SUCCESS_MESSAGES = {
  BLOG_LINKED: "アカウントを連携しました",
  BLOG_UNLINKED: "アカウントを解除しました",
  BLOG_USERNAME_UPDATED: "usernameを更新しました。再同期してください。",
  CAREER_SAVED: "職務経歴書を保存しました。PDF出力できます。",
  CAREER_PDF_DOWNLOADED: "職務経歴書PDFをダウンロードしました。",
} as const;

/**
 * 未ログインお試し入力からログインへ誘導する動線の文言。
 * 職務経歴書を未ログインで入力 → 保存時にログインを促すモーダル / 匿名ヘッダーで使う。
 */
export const AUTH_PROMPT_MESSAGES = {
  /** ログイン促進モーダルの見出し。 */
  TITLE: "ログインして保存しましょう",
  /** ログインで得られる価値の説明。 */
  DESCRIPTION: "ログインすると職務経歴書を保存でき、PDF出力やいつでも編集ができます。",
  /** 入力内容が失われない旨の安心メッセージ。 */
  DRAFT_KEPT: "入力した内容は保持されます。",
  /** GitHub ログインボタン（モーダル）。 */
  GITHUB_LOGIN: "GitHubでログイン",
  /** モーダルを閉じて入力に戻るボタン。 */
  LATER: "あとで",
  /** GitHub へリダイレクト中の表示。 */
  REDIRECTING: "GitHub認証へリダイレクト中...",
  /** 未認証サイドバーのフッターに置くログイン CTA（モーダルとの重複表記を避けて短縮形）。 */
  SIDEBAR_LOGIN: "ログイン",
  /** 未認証時に非活性な連携メニューへ付けるツールチップ。 */
  LOGIN_REQUIRED_HINT: "ログインすると利用できます",
  /** ログイン後、既存の職務経歴書がある場合にドラフトを復元したことを伝える。 */
  DRAFT_RESTORED: "入力内容を復元しました。保存すると既存の職務経歴書を更新します。",
} as const;

/** JSX に直書きされていた UI 文言（ErrorBoundary など） */
export const UI_MESSAGES = {
  ERROR_BOUNDARY_TITLE: "予期しないエラーが発生しました",
  ERROR_BOUNDARY_BODY:
    "ページの表示中に問題が発生しました。再読み込みするか、ホームへ戻ってください。",
  GITHUB_LINK_EMPTY:
    "まだ連携データがありません。連携してアクティビティを可視化しましょう。",
  SIDEBAR_COLLAPSE: "サイドバーを閉じる",
  SIDEBAR_EXPAND: "サイドバーを開く",
  // 未認証フッターの ▲ チェブロン（ダークモード / Issue報告 / 著作権メニュー）の aria-label
  FOOTER_MENU: "メニュー",
  // サイドバーのナビゲーション項目
  NAV_CAREER: "職務経歴書",
  NAV_GITHUB_LINK: "GitHub連携",
  NAV_BLOG_LINK: "ブログ連携",
  // GitHub連携サブパネル
  GITHUB_LINK_OPTIONS: "GitHub連携オプション",
  GITHUB_LINK_RUN: "連携実行",
  GITHUB_INCLUDE_FORKS: "フォークしたリポジトリを含む",
  // ユーザーメニュー（フッター）
  DARK_MODE: "ダークモード",
  LOGOUT: "ログアウト",
  // 認証済みだがユーザー名が取得できない場合のフォールバック表示
  MENU_FALLBACK: "Menu",
  SOURCE_PANEL_COLLAPSE: "原本パネルを閉じる",
  SOURCE_PANEL_EXPAND: "原本パネルを開く",
  // 入力モーダルの × 閉じるボタン（aria-label）
  MODAL_CLOSE: "閉じる",
  // 入力モーダル化したフィールドが未入力のときのプレビュー表示
  FIELD_NOT_ENTERED: "未入力",
  // 入力モーダルへ逃がしたフィールドの表示名（モーダルタイトル / トリガラベル）
  FIELD_SELF_PR: "自己PR",
  FIELD_CAREER_SUMMARY: "職務要約",
  // プレビュー + 編集ボタン（トリガ）の「編集」ラベル
  EDIT: "編集",
  // トースト通知（右上に表示する成功/エラーの一時通知）
  TOAST_REGION_LABEL: "通知",
  TOAST_DISMISS: "通知を閉じる",
  TOAST_ERROR_ID_LABEL: "エラーID:",
  REPORT_ISSUE: "GitHub Issueに報告",
  OPENS_IN_NEW_TAB: "（新しいタブで開きます）",
  COPYRIGHT: "© 2026 DevForge",
  // 職務経歴書ヘッダーのアイコンボタン（aria-label / title 用）
  RESUME_PREVIEW: "プレビュー",
  RESUME_EXPORT_PDF: "PDF出力",
  RESUME_EXPORT_MARKDOWN: "Markdown出力",
  RESUME_DELETE_ALL: "データを削除",
  // 職務経歴書フォームの項目削除アイコン（aria-label / title 用）
  RESUME_DELETE_EXPERIENCE: "職務経歴を削除",
  RESUME_DELETE_CLIENT: "取引先を削除",
  RESUME_DELETE_VACATION: "休業を削除",
  RESUME_DELETE_PROJECT: "プロジェクトを削除",
  RESUME_DELETE_QUALIFICATION: "資格を削除",
  // 職務経歴書「データを削除」確認ダイアログ（ConfirmDialog の message / confirmLabel）
  RESUME_DELETE_CONFIRM:
    "職務経歴書のデータを全て削除します。この操作は取り消せません。本当に削除しますか？",
  RESUME_DELETE_CONFIRM_LABEL: "削除する",
  // 確認ダイアログ共通（ConfirmDialog のボタン文言）
  CONFIRM_DELETING: "削除中...",
  CONFIRM_CANCEL: "キャンセル",
  // ドキュメントフォームの保存ボタン文言（useDocumentForm の saveButtonText）
  FORM_SAVING: "保存中...",
  FORM_UPDATE: "更新する",
  FORM_SAVE: "保存する",
} as const;

/** 外部リンク URL（GitHub リポジトリ / Issue 報告先など）の SSoT */
export const EXTERNAL_LINKS = {
  ISSUE_REPORT: "https://github.com/yusuke0610/devforge/issues",
} as const;

/** GitHub 連携ダッシュボード / コントリビューションヒートマップの UI 文言。 */
export const GITHUB_LINK_MESSAGES = {
  /** アクティビティ（ヒートマップ）セクションの見出し。 */
  ACTIVITY_HEADING: "Activity",
  /** 表示年セレクトの aria-label。 */
  YEAR_SELECT_ARIA: "表示する年",
  /** ヒートマップサマリーの最大連続日数ラベル。 */
  LONGEST_STREAK_LABEL: "最大連続日数",
} as const;

/** 年セレクトの選択肢表記「N年」。 */
export function yearLabel(year: number): string {
  return `${year}年`;
}

/** ヒートマップサマリーの「N年のコントリビュート」ラベル。 */
export function contributionSummaryLabel(year: number): string {
  return `${year}年のコントリビュート`;
}

/** ヒートマップの aria 文言「N年のコントリビューション (合計 M)」。 */
export function contributionAriaLabel(year: number, total: number): string {
  return `${year}年のコントリビューション (合計 ${total})`;
}

/** ファイル取り込み補助（PDF / Markdown 原本上の選択 → 流し込み）UI の文言 */
export const IMPORT_ASSIST_MESSAGES = {
  TITLE: "ファイルから下書きを取り込む",
  HINT: "フォームの入力欄をクリックして選ぶ（緑枠）と、右の原本上で選択した文字がその欄に流し込まれます。テキスト欄は続けて選択で追記できます。",
  SELECT_FILE: "ファイルから取り込み",
  RESELECT_FILE: "ファイルを選び直す",
  RENDERING: "ファイルを表示中...",
  EMPTY: "PDFまたはMarkdownを選ぶと、ここに原本が表示されます。文字をドラッグで選択して入力欄へ流し込めます。",
  /** 空状態のドロップゾーン文言（ドラッグ&ドロップ or クリックで選択）。 */
  DROPZONE: "PDF / Markdown をここにドラッグ＆ドロップ、またはクリックして選択。原本の文字を選ぶと入力欄へ流し込めます。",
  /** ドラッグ中にドロップゾーンへ重ねたときの文言。 */
  DROP_ACTIVE: "ここにドロップして読み込む",
  NO_TEXT:
    "このPDFから文字を選択できませんでした（スキャンPDFの可能性があります）。文字を選択できるPDFをお試しください。",
  RENDER_FAILED: "ファイルの表示に失敗しました。別のファイルをお試しください。",
  /** 対応していない拡張子/形式のファイルが選択された場合。 */
  UNSUPPORTED_TYPE: "対応していない形式です。PDFまたはMarkdown（.md）を選んでください。",
  /** ファイルサイズが上限を超えた場合（ブラウザのフリーズ/メモリ枯渇を防ぐためのガード）。 */
  TOO_LARGE: (limitMb: number) =>
    `ファイルサイズが大きすぎます（上限${limitMb}MB）。ページ数の少ないPDFや、軽量化したファイルをお試しください。`,
  NO_TARGET: "先にフォームの入力欄をクリックして、流し込み先を選んでください。",
  TAB_FALLBACK: "ファイル",
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

/**
 * 経歴書 保存時の変更点確認ダイアログのラベル（セグメント名・フィールド名）。
 * `utils/careerDiff.ts` が「職歴1 ＞ 取引先2 ＞ 案件名」のような人間可読パスを組み立てる際に参照する。
 */
export const CAREER_DIFF_LABELS = {
  // トップレベル
  FULL_NAME: "氏名",
  EMAIL: "メールアドレス",
  GITHUB_URL: "GitHub URL",
  CAREER_SUMMARY: "職務要約",
  SELF_PR: "自己PR",
  // 配列のセグメント名（末尾に連番が付く: 「職歴1」）
  EXPERIENCE: "職歴",
  CLIENT: "取引先",
  PROJECT: "プロジェクト",
  PERIOD: "期間",
  TEAM_MEMBER: "メンバー",
  TECH_STACK: "技術スタック",
  PHASE: "フェーズ",
  QUALIFICATION: "資格",
  // 職歴フィールド
  COMPANY: "会社名",
  BUSINESS_DESCRIPTION: "事業内容",
  START_DATE: "開始年月",
  END_DATE: "終了年月",
  IS_CURRENT: "在職中",
  EMPLOYEE_COUNT: "従業員数",
  CAPITAL: "資本金",
  CAPITAL_UNIT: "資本金単位",
  IS_IT_COMPANY: "IT企業",
  DESCRIPTION: "詳細",
  // 取引先フィールド
  CLIENT_NAME: "取引先名",
  HAS_CLIENT: "取引先あり",
  IS_VACATION: "休暇",
  VACATION_START_DATE: "休暇開始年月",
  VACATION_END_DATE: "休暇終了年月",
  VACATION_IS_CURRENT: "休暇継続中",
  VACATION_DESCRIPTION: "休暇内容",
  // プロジェクトフィールド
  PROJECT_NAME: "案件名",
  ROLE: "役割",
  PROJECT_DESCRIPTION: "案件詳細",
  TEAM_TOTAL: "体制人数",
  // 体制メンバーフィールド
  MEMBER_ROLE: "役割",
  MEMBER_COUNT: "人数",
  // 技術スタックフィールド
  TECH_CATEGORY: "カテゴリ",
  TECH_NAME: "技術名",
  // 資格フィールド
  QUALIFICATION_NAME: "資格名",
  ACQUIRED_DATE: "取得日",
} as const;

/** 経歴書 保存時の変更点確認ダイアログ／左右 diff モーダルの固定文言・表示記号。 */
export const DIFF_DIALOG_MESSAGES = {
  TITLE: "変更内容の確認",
  DESCRIPTION: "保存前に変更点を確認できます。「元に戻す」で項目ごとに編集前の値へ戻せます。",
  CONFIRM: "この内容で保存",
  CANCEL: "キャンセル",
  ROLLBACK: "元に戻す",
  NO_CHANGES: "変更はありません。",
  /** 空文字の値を表示するときの代替テキスト */
  EMPTY_VALUE: "（空）",
  /** パスセグメントの区切り（「職歴1 ＞ 会社名」） */
  PATH_SEPARATOR: " ＞ ",
  /** 種別バッジの文言 */
  ADDED_LABEL: "追加",
  REMOVED_LABEL: "削除",
  MODIFIED_LABEL: "修正",
  /** boolean 値の表示 */
  BOOL_TRUE: "あり",
  BOOL_FALSE: "なし",
  /** 左右 diff ペインの見出し */
  PANE_BASELINE: "保存済み",
  PANE_EDITED: "編集中",
  /** プレビュー生成中・取得失敗・保存済みデータなしの文言 */
  PREVIEW_LOADING: "プレビューを生成中...",
  PREVIEW_FAILED: "プレビューの生成に失敗しました。",
  BASELINE_EMPTY: "保存済みデータがありません。",
  /** 変更点サイドバーの見出し */
  CHANGES_HEADING: "変更点",
} as const;

/** 左右 diff で「変更なし領域」を畳んだときの展開ラベル（件数を埋め込む）。 */
export function foldedSectionLabel(count: number): string {
  return `変更なし ${count} 項目を表示`;
}

/** 左右 diff の編集中ペインで、削除された項目の跡に出すプレースホルダ文言。 */
export function removedStubLabel(text: string): string {
  return `（削除）${text}`;
}

/** ダウンロード失敗時のメッセージにファイル名を付与する。 */
export function downloadFailureMessage(filename: string): string {
  return `${FALLBACK_MESSAGES.DOWNLOAD}: ${filename}`;
}

/** ブログ連携直後の自動同期成功文言（取得件数・合計件数を埋め込む）。 */
export function blogLinkedSyncSuccessMessage(synced: number, total: number): string {
  return `${synced}件の記事を取得しました（合計: ${total}件）`;
}

/** ブログ手動同期の成功文言（新規取得件数・合計件数を埋め込む）。 */
export function blogSyncSuccessMessage(synced: number, total: number): string {
  return `${synced}件の新しい記事を取得しました（合計: ${total}件）`;
}

/** username 更新直後の自動同期成功文言（取得件数・合計件数を埋め込む）。 */
export function blogUsernameUpdatedSyncSuccessMessage(synced: number, total: number): string {
  return `usernameを更新し、${synced}件の記事を取得しました（合計: ${total}件）`;
}

/** 入力モーダルの文字数カウント表示（空白を除いた文字数）。 */
export function charCountLabel(count: number): string {
  return `${count} 文字`;
}

/**
 * Agent チャットウィジェット（ADR-0010）の UI 文言。
 * API 経由のエラー（AGENT_LLM_ERROR 等）は backend messages.json 由来の message を表示し、
 * ここには frontend 完結の文言のみを置く。
 */
export const AGENT_MESSAGES = {
  OPEN_LABEL: "devforge Agent",
  TITLE: "devforge Agent",
  CLOSE_LABEL: "閉じる",
  RESIZE_LABEL: "サイズ変更",
  SCOPE_LABEL: "編集対象",
  SCOPE_CAREER_SUMMARY: "職務要約",
  SCOPE_SELF_PR: "自己PR",
  SCOPE_PROJECT: "プロジェクト",
  SCOPE_EXPERIENCE: "職務経歴",
  TARGET_LABEL: "対象プロジェクト",
  TARGET_EMPTY: "プロジェクトがありません。先に職歴へプロジェクトを追加してください。",
  TARGET_EXPERIENCE_LABEL: "対象職歴",
  TARGET_EXPERIENCE_EMPTY: "職歴がありません。先に職歴を追加してください。",
  TARGET_UNNAMED: "（名称未設定）",
  PROMPT_PLACEHOLDER: "例: 成果がより伝わる文章にしてください",
  SEND: "送信",
  SENDING: "送信中...",
  APPLY: "フォームに反映",
  APPLIED_TOAST: "AI の提案をフォームに反映しました。内容を確認して保存してください。",
  EMPTY_STATE: "編集対象を選んで、改善したい内容を AI に依頼してください。反映後も保存するまで DB は変更されません。",
  LOGIN_REQUIRED: "devforge Agent を使うにはログインが必要です。",
} as const;

/** AI モデル選択（ADR-0012）の UI 文言。製品名（Haiku / Sonnet）は constants/agentModels.ts。 */
export const AGENT_MODEL_MESSAGES = {
  SIDEBAR_LABEL: "使用モデル",
  MENU_ITEM: "AI モデルを切り替え",
  MODAL_TITLE: "AI モデルを選択",
  MODAL_DESCRIPTION:
    "依頼の精度とコストに合わせて選べます。設定はこの端末に保存され、すべての AI 機能で使われます。",
  CLOSE_LABEL: "閉じる",
  CURRENT_BADGE: "選択中",
  FREE_BADGE: "無料",
  PAID_BADGE: "有料",
  INSUFFICIENT_HINT: "残高が不足しています。チャージするか Haiku をご利用ください。",
  HAIKU_TAGLINE: "高速・標準精度。無料で使い放題。",
  HAIKU_COST: "消費クレジット: なし",
  SONNET_TAGLINE: "高精度。重要な仕上げや複雑な依頼に。",
  SONNET_COST: "消費クレジット: 利用したトークン量に応じて",
} as const;

/** クレジット課金（ADR-0012）の UI 文言。 */
export const BILLING_MESSAGES = {
  BALANCE_LOADING: "残高を確認中...",
  SIDEBAR_LABEL: "クレジット残高",
} as const;

/** クレジット残高の数値を 3 桁区切りで整形する（単位ラベルは別途付与）。 */
export function formatCreditAmount(balance: number): string {
  return balance.toLocaleString("ja-JP");
}
