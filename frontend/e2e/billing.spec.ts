import { expect, test, type Page } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * トークン購入画面（ADR-0012）E2E。
 * UserMenu の「クレジットを購入」→ /billing。残高・パック・履歴が表示され、
 * 購入ボタン押下で Stripe Checkout セッションを作成し決済ページへ遷移する（Phase 2）。
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
  // 履歴
  await expect(main.getByText("Agent チャット（sonnet）")).toBeVisible();

  // 任意クレジット入力 → onChange でリアルタイム円換算 + 回数（残高12,000/Sonnet標準12 → ）
  const amountInput = page.getByLabel("購入するクレジット数");
  await amountInput.fill("2000");
  await expect(main.getByText("¥2,000")).toBeVisible();
  await expect(main.getByText(/Sonnet 4\.6 約166回/)).toBeVisible();

  // preset で入力欄が埋まる
  await page.getByRole("button", { name: "1,100" }).click();
  await expect(main.getByText("¥1,100")).toBeVisible();

  // 購入ボタン → Checkout セッション作成 → 返却 URL（決済ページ）へリダイレクト。
  // スタブ URL は baseURL / ポート差異に強くするため現在のページオリジンから動的に組み立てる
  const stubUrl = new URL("/__stripe_stub", page.url()).href;
  await page.route("**/api/billing/checkout", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ checkout_url: stubUrl }),
    }),
  );
  // 外部決済ページの代わりに同一オリジンのスタブへ遷移させ、ナビゲーションを安定させる
  await page.route("**/__stripe_stub", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<html><body>stripe checkout stub</body></html>",
    }),
  );

  const checkoutRequest = page.waitForRequest("**/api/billing/checkout");
  await page.getByRole("button", { name: "購入する" }).click();
  const request = await checkoutRequest;
  expect(request.postDataJSON()).toEqual({ credits: 1100 });
  // 決済ページ（スタブ）へ遷移する
  await expect(page).toHaveURL(/__stripe_stub/);
});
