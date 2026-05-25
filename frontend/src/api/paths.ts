/**
 * バックエンド API パスの SSoT 定数定義。
 *
 * ## 目的
 *
 * - `/api/...` のリテラル文字列が複数のモジュールに散在する SSoT 違反を解消する
 * - backend の router prefix を変更したときに、frontend 側で 404 を起こす前に
 *   静的に検出できるようにする
 *
 * ## 運用ルール
 *
 * - 新規エンドポイントを追加する場合、まず backend `app/routers/*` に `@router.<method>("/...")`
 *   を追加し、その後本ファイルに定数を追加する
 * - パス変更時は本ファイルだけ更新すれば api/*.ts 全体が追従する
 * - 動的パスは関数として export する（例: `resumes.byId(id)`）
 *
 * ## 関連
 *
 * - backend router 定義: `backend/app/routers/*`
 * - 旧来のリテラル参照: `frontend/src/api/*.ts`（本定数経由に置換済み）
 */

export const PATHS = {
  auth: {
    githubCallback: "/auth/github/callback",
    me: "/auth/me",
    githubLoginUrl: "/auth/github/login-url",
    logout: "/auth/logout",
  },
  resumes: {
    base: "/api/resumes",
    latest: "/api/resumes/latest",
    byId: (id: string) => `/api/resumes/${id}`,
    pdf: (id: string) => `/api/resumes/${id}/pdf`,
    markdown: (id: string) => `/api/resumes/${id}/markdown`,
  },
  careerAnalysis: {
    base: "/api/career-analysis/",
    generate: "/api/career-analysis/generate",
    byId: (id: number) => `/api/career-analysis/${id}`,
    status: (id: number) => `/api/career-analysis/${id}/status`,
    retry: (id: number) => `/api/career-analysis/${id}/retry`,
  },
  intelligence: {
    analyze: "/api/intelligence/analyze",
    analyzeRetry: "/api/intelligence/analyze/retry",
    cache: "/api/intelligence/cache",
    cacheStatus: "/api/intelligence/cache/status",
    progress: "/api/intelligence/progress",
  },
  masterData: {
    qualification: "/api/master-data/qualification",
    technologyStack: "/api/master-data/technology-stack",
  },
  notifications: {
    base: "/api/notifications",
    unreadCount: "/api/notifications/unread-count",
    readAll: "/api/notifications/read-all",
    read: (notificationId: string) => `/api/notifications/${notificationId}/read`,
  },
  blog: {
    accounts: "/api/blog/accounts",
    accountByPlatform: (platform: string) => `/api/blog/accounts/${platform}`,
    accountById: (id: string) => `/api/blog/accounts/${id}`,
    accountSync: (accountId: string) => `/api/blog/accounts/${accountId}/sync`,
    articles: (platform?: string) =>
      platform ? `/api/blog/articles?platform=${platform}` : "/api/blog/articles",
    summarize: "/api/blog/summarize",
    summarizeRetry: "/api/blog/summarize/retry",
    summaryCache: "/api/blog/summary-cache",
    summaryCacheStatus: "/api/blog/summary-cache/status",
    score: "/api/blog/score",
  },
  aiResume: {
    generate: "/api/ai-resume/generate",
    snapshots: "/api/ai-resume/snapshots",
    snapshotById: (id: number) => `/api/ai-resume/snapshots/${id}`,
    snapshotFinalize: (id: number) => `/api/ai-resume/snapshots/${id}/finalize`,
    snapshotPdf: (id: number) => `/api/ai-resume/snapshots/${id}/pdf`,
    snapshotMarkdown: (id: number) => `/api/ai-resume/snapshots/${id}/markdown`,
  },
} as const;
