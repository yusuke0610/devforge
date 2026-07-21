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
  DOWNLOAD: "ダウンロードに失敗しました",
  PREVIEW_FETCH: "プレビューの取得に失敗しました",
  AUTH_CHECK: "ログイン状態の確認に失敗しました。",
  GITHUB_OAUTH_START: "GitHub OAuth の開始に失敗しました",
  GITHUB_LINK: "連携に失敗しました",
  AGENT_CHAT: "AI への送信に失敗しました",
  RESUME_DRAFT: "経歴書ドラフトの生成に失敗しました",
  SKILL_FETCH: "スキルの取得に失敗しました",
  SKILL_DISPLAY_PROPOSE: "表示名の提案に失敗しました",
  SKILL_DISPLAY_CONFIRM: "表示名の確定に失敗しました",
  SKILL_DISPLAY_RESET: "表示名の解除に失敗しました",
} as const;

/**
 * 操作成功時にユーザーへ表示する文言（frontend 完結）。
 * backend を経由しない「保存しました」「連携しました」等の success トーストに使う。
 */
export const SUCCESS_MESSAGES = {
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
  // 職務経歴書ページのタイトル見出し
  CAREER_RESUME_TITLE: "職務経歴書",
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

/** 経歴書ドラフト PDF 生成（ADR-0018）の UI 文言。 */
export const RESUME_DRAFT_MESSAGES = {
  /** セクション見出し。 */
  HEADING: "経歴書ドラフト",
  /** 生成ボタンのラベル。 */
  GENERATE: "経歴書ドラフトPDFを生成",
  /** 生成中のボタン/スピナーラベル。 */
  GENERATING: "経歴書ドラフトを生成中...",
  /** 機能説明（モデルはユーザーメニューで選択中のものを使う旨）。 */
  HINT: "連携したリポジトリの情報から、AI が経歴書のたたき台（PDF）を作成します。生成はバックグラウンドで実行され、完了すると通知でお知らせします。使用モデルはユーザーメニューで変更できます。",
  /** 生成物が職務経歴書として保存されない旨の注意書き。 */
  NOT_SAVED_NOTE: "生成した内容は職務経歴書として保存されません。必要な部分は職務経歴書フォームへ転記してください。",
} as const;

/** スキル表示名の human-in-the-loop 確定（ADR-0016 D11）の UI 文言。 */
export const SKILL_DISPLAY_MESSAGES = {
  /** セクション見出し。 */
  HEADING: "スキル",
  /** 機能説明。 */
  HINT: "連携から検出した技術スキルです。AI に読みやすい表示名・まとめ方を提案させ、確認・編集して確定できます。確定した表示名は再連携しても保持されます。",
  /** 提案ボタンのラベル。 */
  PROPOSE: "表示名をAIに提案してもらう",
  /** 提案中のラベル。 */
  PROPOSING: "表示名を提案中...",
  /** レビューパネルの見出し。 */
  REVIEW_HEADING: "表示名の提案（確認して確定してください）",
  /** 表示名入力欄のラベル。 */
  DISPLAY_NAME_LABEL: "表示名",
  /** 確定ボタンのラベル。 */
  CONFIRM: "この内容で確定",
  /** 確定中のラベル。 */
  CONFIRMING: "確定中...",
  /** 提案破棄ボタンのラベル。 */
  DISCARD: "破棄",
  /** スキルが未検出のときの空表示。 */
  EMPTY: "検出されたスキルがありません。先に GitHub 連携を実行してください。",
  /** 提案が 0 件だったときの表示。 */
  PROPOSE_EMPTY: "提案できる表示名がありませんでした。",
  /** 畳み込みメンバー数のラベル接尾（例: 「3 件内包」）。 */
  memberCountLabel: (count: number): string => `${count} 件内包`,
  /** 確定解除（リセット）ボタンのラベル。 */
  RESET: "解除",
  /** 解除中のラベル。 */
  RESETTING: "解除中...",
  /** 解除ボタンの aria-label（対象グループ名を含める）。 */
  resetAriaLabel: (label: string): string => `${label} の表示名確定を解除`,
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

/** AI モデル選択の UI 文言。製品名（Haiku / Sonnet）は constants/agentModels.ts。 */
export const AGENT_MODEL_MESSAGES = {
  SIDEBAR_LABEL: "使用モデル",
  MENU_ITEM: "AI モデルを切り替え",
  MODAL_TITLE: "AI モデルを選択",
  MODAL_DESCRIPTION:
    "依頼の精度に合わせて選べます。設定はこの端末に保存され、すべての AI 機能で使われます。",
  CLOSE_LABEL: "閉じる",
  CURRENT_BADGE: "選択中",
  HAIKU_TAGLINE: "高速・標準精度。日常の依頼に。",
  SONNET_TAGLINE: "高精度。重要な仕上げや複雑な依頼に。",
  GEMINI_FLASH_TAGLINE: "高速・標準精度。日本語も自然。",
  GEMINI_PRO_TAGLINE: "高精度。長文構成や難しい依頼に。",
  GPT_MINI_TAGLINE: "高速・標準精度。構造化出力が得意。",
  GPT_TAGLINE: "高精度・厳格な構造化出力。仕上げに。",
} as const;
