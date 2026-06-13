import { expect, test, type Page } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * トークン購入画面（ADR-0012）E2E。
 * UserMenu の「クレジットを購入」→ /billing。残高・パック・履歴が表示され、
 * 購入ボタン押下で準備中トーストが出る（Stripe 連携は Phase 2）。
 */

async function setupBillingApi(page: Page) {
  await page.route("**/api/billing/balance", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ balance: 12000 }),
    }),
  );
  await page.route("**/api/billing/packs", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { id: "starter", name: "スターター", price_jpy: 500, credits: 500 },
        { id: "standard", name: "スタンダード", price_jpy: 1000, credits: 1100 },
        { id: "pro", name: "プロ", price_jpy: 3000, credits: 3500 },
      ]),
    }),
  );
  await page.route("**/api/billing/transactions", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "t1",
          amount: -270,
          balance_after: 12000,
          transaction_type: "consumption",
          description: "Agent チャット（sonnet）",
          created_at: "2026-06-13T02:00:00Z",
        },
        {
          id: "t2",
          amount: 30000,
          balance_after: 12270,
          transaction_type: "admin_grant",
          description: "テスト付与",
          created_at: "2026-06-12T09:00:00Z",
        },
      ]),
    }),
  );
}

test("UserMenu からトークン購入画面を開き、残高・パック・履歴が表示される", async ({ page }) => {
  await setupAuth(page);
  await setupBillingApi(page);

  await page.goto("/career");
  await waitForAuthenticatedLayout(page);

  await page.getByRole("button", { name: "e2e-test-user" }).click();
  await page.getByRole("button", { name: "クレジットを購入" }).click();

  await expect(page).toHaveURL(/\/billing$/);
  // 残高（サイドバーの残高バッジと区別するため main 内に限定）
  const main = page.locator("main");
  await expect(main.getByText("現在の残高")).toBeVisible();
  await expect(main.getByText("12,000")).toBeVisible();
  // パック（回数アンカー付き。残高12,000 / Sonnet 標準12クレジット → 約1,000回）
  await expect(main.getByText("スターター")).toBeVisible();
  await expect(main.getByText("¥500")).toBeVisible();
  await expect(main.getByText(/Sonnet 約1,000回/)).toBeVisible();
  // 履歴
  await expect(main.getByText("Agent チャット（sonnet）")).toBeVisible();

  // 購入ボタン → 準備中トースト（Stripe は Phase 2）
  await page.getByRole("button", { name: "購入する" }).first().click();
  await expect(
    page.getByText("クレジット購入（Stripe 決済）は現在準備中です。"),
  ).toBeVisible();
});
