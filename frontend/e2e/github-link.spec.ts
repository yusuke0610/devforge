import { test, expect } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * GitHub 連携ダッシュボードでのコントリビューションヒートマップ（年次表示）E2E テスト
 */

test.describe("GitHub 連携 - コントリビューションヒートマップ", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
  });

  test("年セレクタで年を切り替えるとヒートマップの集計が切り替わる", async ({
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
            repos_analyzed: 2,
            unique_skills: 3,
            analyzed_at: "2026-04-24T00:00:00Z",
            languages: { TypeScript: 100 },
            contribution_calendars: [
              {
                year: 2025,
                total_contributions: 256,
                weeks: [[{ date: "2025-01-06", count: 4, level: 2 }]],
              },
              {
                year: 2024,
                total_contributions: 120,
                weeks: [[{ date: "2024-01-01", count: 2, level: 1 }]],
              },
            ],
          },
        }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    // ダッシュボードが表示されること
    await expect(
      page.getByRole("heading", { name: "e2e-test-user の連携結果" }),
    ).toBeVisible();

    // デフォルトは最新年（2025）
    await expect(page.getByRole("heading", { name: "Activity" })).toBeVisible();
    await expect(page.getByText("2025年のコントリビュート")).toBeVisible();
    await expect(page.getByText("256")).toBeVisible();

    // 年セレクタで 2024 に切り替えると集計が切り替わる
    await page
      .getByRole("combobox", { name: "表示する年" })
      .selectOption("2024");
    await expect(page.getByText("2024年のコントリビュート")).toBeVisible();
    await expect(page.getByText("120")).toBeVisible();

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

  test("サイドバーの GitHub連携 クリックは画面遷移のみで連携を実行しない", async ({
    page,
  }) => {
    let runCalled = false;
    await page.route("**/api/github-link/cache", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ result: null, status: null }),
      }),
    );
    await page.route("**/api/github-link/run", (route) => {
      runCalled = true;
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "pending" }),
      });
    });

    // 別ページから GitHub連携 リンクで遷移する
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    await page.getByRole("link", { name: "GitHub連携", exact: true }).click();

    // キャッシュ（空状態）が表示され、連携 API は呼ばれない
    await expect(page).toHaveURL(/\/github_link/);
    await expect(page.getByText(/まだ連携データがありません/)).toBeVisible();
    expect(runCalled).toBe(false);
  });

  test("サブパネルの「連携実行」ボタンで連携が実行されポーリング表示になる", async ({
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

    // ▼ でサブパネルを開き、「連携実行」ボタンを押すと連携が走る
    await page.getByRole("button", { name: "GitHub連携オプション" }).click();
    await page.getByRole("button", { name: "連携実行" }).click();

    await expect(
      page.getByText("GitHubプロフィールを取得中..."),
    ).toBeVisible();
  });
});
