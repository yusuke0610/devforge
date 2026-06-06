import { test, expect, type Page } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 職務経歴書 保存時の文章校正（誤字脱字・表記ゆれ）E2E。
 *
 * 検証:
 * - 保存確認ダイアログ（左右 diff モーダル）に「校正の指摘」セクションが出る。
 * - 自己PR の表記ゆれ（"javascript" → "JavaScript"）が prh で実際に検出され、
 *   worker（textlint + kuromoji 辞書ロード）経由で指摘が画面に出る。
 *
 * 校正はフロント完結（API なし）なので backend モック不要。worker が public/kuromoji-dict/
 * から辞書をロードするため、指摘表示には余裕を持った待機を取る。
 */
async function setupResumeApi(page: Page) {
  const baseResume = {
    id: "resume-1",
    full_name: "山田 太郎",
    career_summary: "サマリー",
    // 表記ゆれ（javascript）を含む自己PR。
    self_pr: "私はjavascriptが得意です。",
    experiences: [],
    qualifications: [],
  };

  await page.route("**/api/master-data/qualification", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/master-data/technology-stack", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/resumes/preview", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ html: "<div>preview</div>", css: "" }),
    }),
  );
  await page.route("**/api/resumes/latest", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(baseResume),
    }),
  );
}

test.describe("職務経歴書 保存時の文章校正", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupResumeApi(page);
  });

  test("保存確認ダイアログに校正の指摘（表記ゆれ）が表示される", async ({ page }) => {
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // 変更を作って確認ダイアログを開く（氏名を編集）。
    await page.getByPlaceholder("例: 山田 太郎").fill("佐藤 花子");
    await page.getByRole("button", { name: /更新する|保存する/ }).click();

    // ダイアログと統合レビュー一覧（変更点＋校正）が出る。
    await expect(page.getByRole("dialog", { name: "変更内容の確認" })).toBeVisible();
    await expect(page.getByText("変更点・校正", { exact: true })).toBeVisible();

    // prh による表記ゆれ指摘（javascript => JavaScript）が worker 経由で表示される。
    // 辞書ロードを含むため待機時間を長めに取る。
    await expect(page.getByText(/JavaScript/)).toBeVisible({ timeout: 30000 });

    // 校正があっても保存はブロックされない（「この内容で保存」が押せる）。
    await expect(page.getByRole("button", { name: "この内容で保存" })).toBeEnabled();
  });
});
