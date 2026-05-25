/**
 * MSW リクエストハンドラー定義。
 * テストデータに機密情報（氏名・住所・トークン等）を含めないこと。
 */
import { http, HttpResponse } from "msw";

/** 正常系: 認証済みユーザー */
const authMe = http.get("*/auth/me", () =>
  HttpResponse.json({ username: "test-user-001", is_github_user: true }),
);

/** 正常系: GitHub 分析開始（202 Accepted） */
const analyzeGitHub = http.post("*/api/intelligence/analyze", () =>
  HttpResponse.json({ status: "pending" }, { status: 202 }),
);

/** 正常系: 分析キャッシュステータス（completed） */
const analysisCacheStatusCompleted = http.get(
  "*/api/intelligence/cache/status",
  () => HttpResponse.json({ status: "completed" }),
);

/** 正常系: 分析キャッシュ結果 */
const analysisCacheResult = http.get("*/api/intelligence/cache", () =>
  HttpResponse.json({
    status: "completed",
    analysis_result: {
      username: "test-user-001",
      repos_analyzed: 10,
      unique_skills: 5,
      analyzed_at: "2026-01-01T00:00:00Z",
      languages: { TypeScript: 60, Python: 40 },
      detected_frameworks: { React: 3, FastAPI: 2 },
      detected_devtools: { Docker: 4, "GitHub Actions": 3 },
      detected_infras: { Terraform: 1 },
    },
  }),
);

/** デフォルトハンドラー */
export const handlers = [
  authMe,
  analyzeGitHub,
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
  analyzeServerError: http.post("*/api/intelligence/analyze", () =>
    HttpResponse.json(
      { detail: "Internal Server Error" },
      { status: 500 },
    ),
  ),
  /** 分析失敗 */
  analysisCacheStatusFailed: http.get(
    "*/api/intelligence/cache/status",
    () =>
      HttpResponse.json({
        status: "dead_letter",
        error_message: "LLM タイムアウト",
      }),
  ),
};
