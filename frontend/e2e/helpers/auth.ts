import type { Page } from "@playwright/test";

/** テスト用認証済みユーザー情報 */
export const TEST_USER = {
  username: "e2e-test-user",
  is_github_user: true,
};

/**
 * 認証済み状態をセットアップする。
 *
 * Playwright のルートは LIFO（後登録が優先）。
 * 汎用キャッチオールを先に、具体的なモックを後から登録することで
 * 具体的なモックが優先される。
 */
export async function setupAuth(page: Page) {
  // ① キャッチオール（最低優先）: localhost:8000 への全リクエストを 404 で即返し
  // LoadingOverlay が残り続けるのを防ぐ。
  // **/api/** は Vite の src/api/*.ts も傍受するため、ホスト名で絞り込む
  await page.route("http://localhost:8000/**", (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ code: "NOT_FOUND", message: "not found" }),
    }),
  );

  // ② 具体的なモック（キャッチオールより後に登録 = 高優先）

  // 通知一覧をモック
  await page.route("**/api/notifications", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }),
  );

  // 通知未読件数をモック（デフォルト: 0）
  await page.route("**/api/notifications/unread-count", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ count: 0 }),
    }),
  );

  // クレジット残高をモック（サイドバーが認証済み全ページで取得する / ADR-0012。デフォルト: 0）
  await page.route("**/api/billing/balance", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ balance: 0 }),
    }),
  );

  // 認証 API をモック（最高優先）
  await page.route("**/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(TEST_USER),
    }),
  );
}

/**
 * 認証済みレイアウトが表示され、ローディング状態が終了するまで待機する。
 */
export async function waitForAuthenticatedLayout(page: Page) {
  // サイドバータイトルが表示されるまで待つ
  await page.waitForSelector("text=DevForge", { timeout: 10_000 });
  // LoadingOverlay が消えるまで待つ（position:fixed でサイドバーを覆う可能性がある）
  await page.waitForSelector("[class*='loadingOverlay']", {
    state: "hidden",
    timeout: 10_000,
  });
}
