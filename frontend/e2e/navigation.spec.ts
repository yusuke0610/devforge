import { test, expect } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * サイドバーナビゲーション E2E テスト
 */

test.describe("認証済みユーザーのナビゲーション", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("サイドバーが表示される", async ({ page }) => {
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // Agent FAB（aria-label: devforge Agent）と二重マッチしないよう exact 指定
    await expect(page.getByText("DevForge", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "職務経歴書" })).toBeVisible();
    // GitHub連携 は画面遷移に徹するためリンク（連携実行はサブパネルのボタン）
    await expect(
      page.getByRole("link", { name: "GitHub連携", exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "ブログ連携" })).toBeVisible();
  });

  test("通知ベルがサイドバーに表示される", async ({ page }) => {
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);
    await expect(page.getByRole("button", { name: /通知/ })).toBeVisible();
  });

  test("ページ間のナビゲーションが動作する", async ({ page }) => {
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    await page.getByRole("link", { name: "ブログ連携" }).click();
    await expect(page).toHaveURL(/\/blog/);
  });
});
