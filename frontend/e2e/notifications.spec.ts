import { test, expect } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 通知ベル E2E テスト
 */

test.describe("通知ベル", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("未読なしのとき通知ベルにバッジが表示されない", async ({ page }) => {
    // setupAuth で unread-count は count: 0 が返るよう設定済み
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    const bell = page.getByRole("button", { name: /通知/ });
    await expect(bell).toBeVisible();
    // バッジ（数字）が存在しないことを確認
    await expect(bell.locator("[class*='badge']")).not.toBeVisible();
  });

  test("未読通知があるときバッジが表示される", async ({ page }) => {
    // 最後に登録したハンドラーが優先されるため setupAuth のものを上書き
    await page.route("**/api/notifications/unread-count", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 3 }),
      }),
    );

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // バッジに "3" が表示されることを確認
    const bell = page.getByRole("button", { name: /通知/ });
    await expect(bell.getByText("3")).toBeVisible();
  });

  test("ベルをクリックすると通知パネルが開く", async ({ page }) => {
    const mockNotifications = [
      {
        id: "notif-1",
        task_type: "github_analysis",
        status: "completed",
        title: "GitHub分析が完了しました",
        message: null,
        is_read: false,
        created_at: new Date().toISOString(),
      },
      {
        id: "notif-2",
        task_type: "github_analysis",
        status: "failed",
        title: "GitHub分析に失敗しました",
        message: null,
        is_read: false,
        created_at: new Date().toISOString(),
      },
    ];

    await page.route("**/api/notifications/unread-count", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 1 }),
      }),
    );
    await page.route("**/api/notifications", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(mockNotifications),
      }),
    );

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);
    await page.getByRole("button", { name: /通知/ }).click();

    // パネルが開いてタイトルが見える
    await expect(page.getByText("GitHub分析が完了しました")).toBeVisible();
    await expect(page.getByText("GitHub分析に失敗しました")).toBeVisible();
  });

  test("「全て既読」ボタンをクリックするとバッジが消える", async ({ page }) => {
    await page.route("**/api/notifications/unread-count", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ count: 2 }),
      }),
    );
    await page.route("**/api/notifications", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "notif-1",
            task_type: "github_analysis",
            status: "completed",
            title: "GitHub分析が完了しました",
            message: null,
            is_read: false,
            created_at: new Date().toISOString(),
          },
        ]),
      }),
    );
    await page.route("**/api/notifications/read-all", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ updated: 2 }),
      }),
    );

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    const bell = page.getByRole("button", { name: /通知/ });
    await expect(bell.getByText("2")).toBeVisible();

    await bell.click();
    await page.getByRole("button", { name: "全て既読" }).click();

    // バッジが消えることを確認
    await expect(bell.locator("[class*='badge']")).not.toBeVisible();
  });

  test("パネル外をクリックすると閉じる", async ({ page }) => {
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    await page.getByRole("button", { name: /通知/ }).click();
    await expect(page.getByText("通知はありません")).toBeVisible();

    // メインコンテンツエリアをクリックしてパネルを閉じる
    await page.locator("main").click({ position: { x: 100, y: 100 } });
    await expect(page.getByText("通知はありません")).not.toBeVisible();
  });
});
