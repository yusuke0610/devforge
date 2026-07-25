import { expect, test, type Page } from "@playwright/test";

import { RESUME_IMPORT_MESSAGES } from "../src/constants/messages";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 手持ち PDF 経歴書のフォーム流し込み（ADR-0024 / #528）E2E。
 *
 * シナリオ:
 * 1. 空フォームの新規ユーザは「PDF から自動入力」パネルを見る
 * 2. PDF をアップロード（POST /api/agent/resume-import/pdf をモック）
 * 3. 抽出結果がフォーム（氏名・職務要約・自己PR）に反映される（DB 非更新）
 * 4. 反映成功のトーストが出る
 */

/** 職務経歴書の最小 API モック。latest は 404 = 空フォーム（パネルが出る条件）。 */
async function setupEmptyResume(page: Page) {
  await page.route("**/api/master-data/qualification", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/master-data/technology-stack", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/resumes/latest", (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ code: "NOT_FOUND", message: "not found" }),
    }),
  );
}

test.describe("PDF 経歴書インポート", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupEmptyResume(page);
  });

  test("空フォームで PDF をアップロードすると抽出結果が反映される", async ({ page }) => {
    await page.route("**/api/agent/resume-import/pdf", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          full_name: "山田 太郎",
          career_summary: "バックエンドエンジニアとして 5 年の経験があります。",
          self_pr: "品質と保守性を重視した設計が得意です。",
          experiences: [
            {
              company: "株式会社サンプル",
              business_description: "受託開発",
              start_date: "2020-04",
              end_date: "2023-03",
              description: "API 開発を担当。",
            },
          ],
        }),
      });
    });

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // 空フォームの新規ユーザにパネルが見える
    await expect(page.getByText(RESUME_IMPORT_MESSAGES.HEADING)).toBeVisible();

    // 隠しファイル input に PDF を投入する（マジックバイト付きのダミー）
    await page
      .getByLabel(RESUME_IMPORT_MESSAGES.UPLOAD_LABEL)
      .setInputFiles({
        name: "resume.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.7\n...dummy..."),
      });

    // 抽出結果がフォームへ反映される（空フォームなので確認ダイアログは出ない）
    await expect(page.getByText(RESUME_IMPORT_MESSAGES.APPLIED_TOAST)).toBeVisible();
    // 氏名入力に抽出値が入る
    await expect(page.getByPlaceholder("例: 山田 太郎")).toHaveValue("山田 太郎");
  });

  test("非対応 PDF（スキャン）はエラーメッセージを表示する", async ({ page }) => {
    await page.route("**/api/agent/resume-import/pdf", async (route) => {
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({
          code: "VALIDATION_ERROR",
          message: "テキストを含む PDF のみ対応しています。スキャン画像の PDF は読み取れないため、お手数ですが手入力をお願いします。",
        }),
      });
    });

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    await page
      .getByLabel(RESUME_IMPORT_MESSAGES.UPLOAD_LABEL)
      .setInputFiles({
        name: "scan.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("%PDF-1.7\n...scan..."),
      });

    await expect(page.getByText(/テキストを含む PDF のみ対応/)).toBeVisible();
  });
});
