import { test, expect } from "@playwright/test";

import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 認証フロー E2E テスト
 *
 * 動線方針: 未ログインでも職務経歴書を入力でき（お試し入力）、保存時にログインを促す。
 * `/career` はログイン強制せず、`/login` は明示ログイン・OAuth エラー着地用に残す。
 */

/** localhost:8000 への全リクエストを 404 で返すキャッチオール（master-data 等を解決させる）。 */
async function routeBackendNotFound(page: import("@playwright/test").Page) {
  await page.route("http://localhost:8000/**", (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ code: "NOT_FOUND", message: "not found" }),
    }),
  );
}

test.describe("未認証ユーザー（お試し入力）", () => {
  test("ルート / は /login ではなく職務経歴書のお試し入力画面を表示する", async ({ page }) => {
    await routeBackendNotFound(page);
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      }),
    );

    await page.goto("/");

    // /login へリダイレクトされず、職務経歴書フォームが表示される
    await expect(page.getByRole("heading", { name: "職務経歴書" })).toBeVisible();
    await expect(page).toHaveURL(/\/career/);
    // 氏名を入力できる（お試し入力）
    await page.getByPlaceholder("例: 山田 太郎").fill("山田太郎");
    await expect(page.getByPlaceholder("例: 山田 太郎")).toHaveValue("山田太郎");

    // サイドバー: ユーザーメニュー位置にログイントリガーが表示される
    await expect(page.getByRole("button", { name: "ログイン" })).toBeVisible();
    // GitHub連携 / ブログ連携 は表示され、押下でログイン導線になる（非活性ではない）
    await expect(page.getByRole("button", { name: "GitHub連携" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "ブログ連携" })).toBeEnabled();
  });

  test("未ログインで連携メニューを押すとログイン促進モーダルが出る", async ({ page }) => {
    await routeBackendNotFound(page);
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      }),
    );

    await page.goto("/career");
    await page.getByRole("button", { name: "GitHub連携" }).click();
    await expect(
      page.getByRole("heading", { name: "ログインして保存しましょう" }),
    ).toBeVisible();
  });

  test("未ログインでプレビューを押すとログイン促進モーダルが出る", async ({ page }) => {
    await routeBackendNotFound(page);
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      }),
    );

    await page.goto("/career");
    await page.getByRole("button", { name: "プレビュー" }).click();
    await expect(
      page.getByRole("heading", { name: "ログインして保存しましょう" }),
    ).toBeVisible();
  });

  test("未ログインで保存しようとするとログイン促進モーダルが出る", async ({ page }) => {
    let loginUrlRequest: string | null = null;

    await routeBackendNotFound(page);
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      }),
    );
    await page.route("**/auth/github/login-url*", (route) => {
      loginUrlRequest = route.request().url();
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authorization_url: "http://localhost:5173/mock-github-oauth",
          state: "mock-state",
        }),
      });
    });
    await page.route("**/mock-github-oauth*", (route) =>
      route.fulfill({ status: 200, contentType: "text/html", body: "<html></html>" }),
    );

    await page.goto("/career");
    await page.getByPlaceholder("例: 山田 太郎").fill("山田太郎");
    await page.getByRole("button", { name: "保存する" }).click();

    // ログイン促進モーダルが表示される
    await expect(
      page.getByRole("heading", { name: "ログインして保存しましょう" }),
    ).toBeVisible();

    // 入力ドラフトが sessionStorage に退避される（ログイン往復で失わないため）
    expect(
      await page.evaluate(() => sessionStorage.getItem("career_draft")),
    ).toContain("山田太郎");

    // モーダルの GitHub ログインで OAuth 開始 URL が呼ばれる
    await page.getByRole("button", { name: "GitHubでログイン" }).click();
    await expect.poll(() => loginUrlRequest).not.toBeNull();
    expect(loginUrlRequest).toContain("/auth/github/login-url");
    expect(loginUrlRequest).toContain("return_to=");
  });

  test("退避ドラフトはログイン後に自動保存され失われない（新規ユーザー）", async ({ page }) => {
    // 認証済み（サイドバー付き）状態をセットアップ。
    await setupAuth(page);
    // API はホスト名非依存（Vite プロキシ経由のため）でモックする。
    // 未モックの /api/* が実バックエンドに到達して 401 を返すと _onUnauthorized で
    // 匿名へ戻ってしまうため、必要なエンドポイントをすべて塞ぐ。
    await page.route("**/api/master-data/qualification", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    await page.route("**/api/master-data/technology-stack", (route) =>
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
    );
    // 新規ユーザー: 既存経歴書なし（404）。
    await page.route("**/api/resumes/latest", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ code: "NOT_FOUND", message: "not found" }),
      }),
    );
    // 自動保存の POST を捕捉する。
    let createdName: string | null = null;
    await page.route("**/api/resumes", (route) => {
      if (route.request().method() === "POST") {
        createdName = route.request().postDataJSON()?.full_name ?? null;
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: "new-resume-id",
            full_name: createdName ?? "",
            career_summary: "",
            self_pr: "",
            experiences: [],
            qualifications: [],
          }),
        });
      }
      return route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
    });

    // ログイン往復から復帰した状態を再現するため、アプリ起動前にドラフトを sessionStorage へ仕込む。
    await page.addInitScript(() => {
      sessionStorage.setItem(
        "career_draft",
        JSON.stringify({
          full_name: "山田太郎",
          career_summary: "テスト要約",
          self_pr: "テスト自己PR",
          experiences: [
            {
              company: "株式会社テスト",
              business_description: "受託開発",
              start_date: "2020-04",
              end_date: null,
              is_current: true,
              is_it_company: true,
              description: "",
              employee_count: "100",
              capital: "1",
              capital_unit: "万円",
              clients: [],
            },
          ],
          qualifications: [],
        }),
      );
    });

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);
    // サイドバーのナビゲーション（認証済みレイアウト専用）が出ていることを確認する。
    await expect(page.getByRole("link", { name: "職務経歴書" })).toBeVisible();

    // 退避ドラフトが自動保存（POST）され、入力した氏名が送られる。
    await expect.poll(() => createdName).toBe("山田太郎");
    // フォームにも氏名が反映され、入力は失われていない。
    await expect(page.getByPlaceholder("例: 山田 太郎")).toHaveValue("山田太郎");
    // 退避領域は消費後に破棄される。
    await expect
      .poll(() => page.evaluate(() => sessionStorage.getItem("career_draft")))
      .toBeNull();
  });
});

test.describe("ログイン画面", () => {
  test("/login の GitHubでログインボタンを押すと /auth/github/login-url が呼ばれる", async ({
    page,
  }) => {
    let loginUrlRequest: string | null = null;

    await routeBackendNotFound(page);
    await page.route("**/auth/me", (route) =>
      route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      }),
    );
    await page.route("**/auth/github/login-url*", (route) => {
      loginUrlRequest = route.request().url();
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          authorization_url: "http://localhost:5173/mock-github-oauth",
          state: "mock-state",
        }),
      });
    });
    await page.route("**/mock-github-oauth*", (route) =>
      route.fulfill({ status: 200, contentType: "text/html", body: "<html></html>" }),
    );

    await page.goto("/login");
    await page.getByRole("button", { name: "GitHubでログイン" }).click();
    await expect.poll(() => loginUrlRequest).not.toBeNull();
    expect(loginUrlRequest).toContain("/auth/github/login-url");
    expect(loginUrlRequest).toContain("return_to=");
  });
});
