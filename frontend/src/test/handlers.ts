/**
 * MSW リクエストハンドラー定義。
 * テストデータに機密情報（氏名・住所・トークン等）を含めないこと。
 */
import { http, HttpResponse } from "msw";

/** 正常系: 認証済みユーザー */
const authMe = http.get("*/auth/me", () =>
  HttpResponse.json({ username: "test-user-001", is_github_user: true }),
);

/** 正常系: GitHub 連携開始（202 Accepted） */
const runGitHubLink = http.post("*/api/github-link/run", () =>
  HttpResponse.json({ status: "pending" }, { status: 202 }),
);

/** 正常系: 連携キャッシュステータス（completed） */
const analysisCacheStatusCompleted = http.get(
  "*/api/github-link/cache/status",
  () => HttpResponse.json({ status: "completed" }),
);

/** 正常系: 連携キャッシュ結果 */
const analysisCacheResult = http.get("*/api/github-link/cache", () =>
  HttpResponse.json({
    status: "completed",
    result: {
      username: "test-user-001",
      repos_analyzed: 10,
      unique_skills: 5,
      analyzed_at: "2026-01-01T00:00:00Z",
      languages: { TypeScript: 60, Python: 40 },
      contribution_calendars: [
        {
          year: 2025,
          total_contributions: 123,
          weeks: [
            [
              { date: "2025-01-06", count: 2, level: 1 },
              { date: "2025-01-07", count: 8, level: 4 },
            ],
          ],
        },
        {
          year: 2024,
          total_contributions: 88,
          weeks: [
            [
              { date: "2024-01-01", count: 1, level: 1 },
              { date: "2024-01-02", count: 5, level: 3 },
            ],
          ],
        },
      ],
    },
  }),
);

/** デフォルトハンドラー */
export const handlers = [
  authMe,
  runGitHubLink,
  analysisCacheStatusCompleted,
  analysisCacheResult,
];

/** エラーシナリオ用（server.use() でオーバーライドして使う） */
export const errorHandlers = {
  /** 認証エラー: 401 */
  unauthorized: http.get("*/auth/me", () =>
    HttpResponse.json({ detail: "Unauthorized" }, { status: 401 }),
  ),
  /** サーバーエラー: 500 */
  analyzeServerError: http.post("*/api/github-link/run", () =>
    HttpResponse.json(
      { detail: "Internal Server Error" },
      { status: 500 },
    ),
  ),
  /** 連携失敗 */
  analysisCacheStatusFailed: http.get(
    "*/api/github-link/cache/status",
    () =>
      HttpResponse.json({
        status: "dead_letter",
        error_message: "分析処理がタイムアウトしました",
      }),
  ),
};
