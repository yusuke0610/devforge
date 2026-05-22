import { test, expect, type Page } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 職務経歴書の未保存マーク（🔴）E2E。
 *
 * シナリオ:
 * 1. 職務経歴書を開く → 🔴 なし
 * 2. 氏名を編集 → 氏名横と保存ボタン横に 🔴
 * 3. キャリア分析タブへ遷移して職務経歴書に戻る → 🔴 が維持されている（Redux 保持）
 * 4. 保存（PUT /api/resumes/{id}）→ baseline 更新で 🔴 が全消失
 */

/** 職務経歴書の API モックをまとめてセットする */
async function setupResumeApi(page: Page) {
  const baseResume = {
    id: "resume-1",
    full_name: "山田 太郎",
    career_summary: "サマリー",
    self_pr: "自己PR",
    experiences: [
      {
        company: "株式会社A",
        business_description: "受託開発",
        start_date: "2020-04",
        end_date: null,
        is_current: true,
        employee_count: "100",
        capital: "1",
        clients: [],
      },
    ],
    qualifications: [],
  };

  // マスタデータ
  await page.route("**/api/master-data/qualification", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/master-data/technology-stack", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );

  // 最新取得
  await page.route("**/api/resumes/latest", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(baseResume),
    }),
  );

  // 更新（PUT）。レスポンスは編集後の値で返す前提だが、テストでは保存後 🔴 が消えれば良いので
  // request 内容をそのまま baseline として返す。
  await page.route("**/api/resumes/resume-1", async (route) => {
    if (route.request().method() === "PUT") {
      const body = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...baseResume, ...body }),
      });
      return;
    }
    await route.fallback();
  });

  // キャリア分析ページ用モック（タブ遷移先の 404 ループを避ける）
  await page.route("**/api/career-analysis/**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}

test.describe("職務経歴書 未保存マーク", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupResumeApi(page);
  });

  test("編集 → 🔴 表示 → タブ遷移後も維持 → 保存で消える", async ({ page }) => {
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // 1. 初期状態: 🔴 は出ていない
    await expect(page.getByTestId("dirty-dot")).toHaveCount(0);

    // 2. 氏名を編集
    const nameInput = page.getByPlaceholder("例: 山田 太郎");
    await nameInput.fill("佐藤 花子");

    // 🔴 が 1 つ以上現れる（氏名 label + 保存ボタン横、計 2 以上）
    await expect(page.getByTestId("dirty-dot").first()).toBeVisible();
    const dirtyCountAfterEdit = await page.getByTestId("dirty-dot").count();
    expect(dirtyCountAfterEdit).toBeGreaterThanOrEqual(2);

    // 3. キャリア分析タブへ遷移
    await page.getByRole("link", { name: "キャリア分析" }).click();
    await expect(page).toHaveURL(/\/career_analysis/);

    // 職務経歴書に戻る
    await page.getByRole("link", { name: "職務経歴書" }).click();
    await expect(page).toHaveURL(/\/career$/);
    await waitForAuthenticatedLayout(page);

    // 編集値と 🔴 が維持されている
    await expect(nameInput).toHaveValue("佐藤 花子");
    const dirtyCountAfterReturn = await page.getByTestId("dirty-dot").count();
    expect(dirtyCountAfterReturn).toBeGreaterThanOrEqual(2);

    // 4. 保存 → 🔴 が全消失
    await page.getByRole("button", { name: /更新する|保存する/ }).click();
    await expect(page.getByTestId("dirty-dot")).toHaveCount(0);
  });
});
