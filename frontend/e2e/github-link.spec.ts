import { test, expect } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * GitHub 連携ダッシュボードでの検出フレームワーク表示 E2E テスト（Issue #203）
 */

test.describe("GitHub 連携 - 検出フレームワーク表示", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("検出フレームワークが Frameworks セクションに表示される", async ({
    page,
  }) => {
    // 連携キャッシュのモックを登録（キャッチオールより後 = 優先される）
    await page.route("**/api/github-link/cache", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "completed",
          result: {
            username: "e2e-test-user",
            repos_analyzed: 3,
            unique_skills: 5,
            analyzed_at: "2026-04-24T00:00:00Z",
            languages: { TypeScript: 60000, Python: 40000 },
            detected_frameworks: { React: 5, "Next.js": 3, FastAPI: 2 },
            position_scores: null,
          },
          position_advice: null,
        }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    // ダッシュボードが表示されること
    await expect(
      page.getByRole("heading", { name: "e2e-test-user の連携結果" }),
    ).toBeVisible();

    // Frameworks セクションが存在し、各 framework 名が表示されること
    await expect(
      page.getByRole("heading", { name: "Frameworks" }),
    ).toBeVisible();
    const list = page.getByRole("list", { name: "検出フレームワーク一覧" });
    await expect(list).toBeVisible();
    await expect(list.getByText("React")).toBeVisible();
    await expect(list.getByText("Next.js")).toBeVisible();
    await expect(list.getByText("FastAPI")).toBeVisible();
  });

  test("検出フレームワークが空のとき Frameworks セクションが出ない", async ({
    page,
  }) => {
    await page.route("**/api/github-link/cache", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "completed",
          result: {
            username: "e2e-test-user",
            repos_analyzed: 1,
            unique_skills: 0,
            analyzed_at: "2026-04-24T00:00:00Z",
            languages: { TypeScript: 100 },
            detected_frameworks: [],
            position_scores: null,
          },
          position_advice: null,
        }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    await expect(
      page.getByRole("heading", { name: "e2e-test-user の連携結果" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Frameworks" }),
    ).not.toBeVisible();
  });

  test("コントリビューションカレンダーがあると Activity ヒートマップが表示される", async ({
    page,
  }) => {
    await page.route("**/api/github-link/cache", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "completed",
          result: {
            username: "e2e-test-user",
            repos_analyzed: 2,
            unique_skills: 3,
            analyzed_at: "2026-04-24T00:00:00Z",
            languages: { TypeScript: 100 },
            detected_frameworks: {},
            detected_devtools: {},
            detected_infras: {},
            contribution_calendar: {
              total_contributions: 256,
              weeks: [[{ date: "2025-01-06", count: 4, level: 2 }]],
            },
          },
        }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    await expect(
      page.getByRole("heading", { name: "Activity" }),
    ).toBeVisible();
    await expect(page.getByText("年間コントリビュート")).toBeVisible();
    await expect(page.getByText("256")).toBeVisible();

    // ページは表示専用。連携トリガーボタン（更新する/再連携）は無い
    await expect(
      page.getByRole("button", { name: "更新する" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "再連携" }),
    ).toHaveCount(0);
  });

  test("未連携時は空状態メッセージが表示され、ページに連携ボタンが無い", async ({
    page,
  }) => {
    await page.route("**/api/github-link/cache", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ result: null, status: null }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    await expect(page.getByText(/まだ連携データがありません/)).toBeVisible();
    // トリガーはサイドバーのみ。ページ本文に連携ボタンは無い
    await expect(
      page.getByRole("button", { name: "連携する" }),
    ).toHaveCount(0);
  });

  test("サイドバーの ▾ でフォーク含むオプションが開閉する", async ({
    page,
  }) => {
    await page.route("**/api/github-link/cache", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ result: null, status: null }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    // デフォルトでは非表示
    await expect(
      page.getByText("フォークしたリポジトリを含む"),
    ).toHaveCount(0);

    await page
      .getByRole("button", { name: "GitHub連携オプション" })
      .click();

    await expect(
      page.getByText("フォークしたリポジトリを含む"),
    ).toBeVisible();
  });

  test("サイドバーの GitHub連携 クリックで連携が実行されポーリング表示になる", async ({
    page,
  }) => {
    await page.route("**/api/github-link/cache", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ result: null, status: null }),
      }),
    );
    await page.route("**/api/github-link/run", (route) =>
      route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "pending" }),
      }),
    );
    await page.route("**/api/github-link/cache/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "pending" }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    await page
      .getByRole("button", { name: "GitHub連携", exact: true })
      .click();

    await expect(
      page.getByText("GitHubプロフィールを取得中..."),
    ).toBeVisible();
  });
});
