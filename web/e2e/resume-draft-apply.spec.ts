import { expect, test, type Page } from "@playwright/test";

import { RESUME_DRAFT_MESSAGES } from "../src/constants/messages";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 経歴書ドラフトのフォーム流し込み（ADR-0025 / #525）E2E。
 *
 * シナリオ:
 * 1. GitHub 連携済みユーザがドラフトを生成（enqueue→完了→PDF プレビュー）
 * 2. 「この内容をフォームに反映」を押すと payload を取得して /career へ遷移
 * 3. 空フォーム（保存済み経歴書なし）にドラフト内容が反映される（DB 非更新）
 */

async function setupDraftAndCareer(page: Page) {
  await page.route("**/api/github-link/cache", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "completed",
        result: {
          username: "e2e-test-user",
          repos_analyzed: 1,
          unique_skills: 1,
          analyzed_at: "2026-04-24T00:00:00Z",
          languages: { TypeScript: 100 },
        },
      }),
    }),
  );
  await page.route("**/api/github-link/skills", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ skills: [] }) }),
  );
  // ドラフト生成フロー（enqueue→完了→PDF）
  await page.route("**/api/agent/resume-draft/status", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "completed" }) }),
  );
  await page.route("**/api/agent/resume-draft/run", (route) =>
    route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ status: "pending" }) }),
  );
  await page.route("**/api/agent/resume-draft/pdf", (route) =>
    route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n%mock\n" }),
  );
  // payload 取得（フォーム反映用）
  await page.route("**/api/agent/resume-draft/result", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        full_name: "ドラフト 太郎",
        email: "",
        github_url: "https://github.com/e2e-test-user",
        career_summary: "GitHub から生成した職務要約。",
        self_pr: "生成した自己PR。",
        experiences: [
          {
            company: "株式会社ドラフト",
            business_description: "自社開発",
            start_date: "2020-04",
            end_date: "",
            is_current: true,
            clients: [],
          },
        ],
        qualifications: [],
      }),
    }),
  );
  // /career 側: 保存済み経歴書なし（空フォーム）+ マスタ空
  await page.route("**/api/resumes/latest", (route) =>
    route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ code: "NOT_FOUND", message: "not found" }) }),
  );
  await page.route("**/api/master-data/qualification", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/master-data/technology-stack", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}

test.describe("ドラフトのフォーム流し込み", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupDraftAndCareer(page);
  });

  test("ドラフト生成→フォームに反映で /career にドラフト内容が入る", async ({ page }) => {
    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    // ドラフト生成 → PDF プレビューが開く
    await page.getByRole("button", { name: "経歴書ドラフトPDFを生成" }).click();
    await expect(page.getByText("PDFプレビュー")).toBeVisible();

    // 「この内容をフォームに反映」→ /career へ遷移
    await page.getByRole("button", { name: RESUME_DRAFT_MESSAGES.APPLY_TO_FORM }).click();

    await expect(page).toHaveURL(/\/career$/);
    // 空フォームなので確認ダイアログなしで反映され、氏名にドラフト値が入る
    await expect(page.getByText(RESUME_DRAFT_MESSAGES.APPLIED_TOAST)).toBeVisible();
    await expect(page.getByPlaceholder("例: 山田 太郎")).toHaveValue("ドラフト 太郎");
  });
});
