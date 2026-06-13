import { test, expect, type Page } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * Agent チャットウィジェット（ADR-0010）E2E。
 *
 * シナリオ:
 * 1. 職務経歴書を開く → 右下に「devforge Agent」ボタン
 * 2. チャットを開き、職務要約スコープでプロンプト送信（POST /api/agent/chat をモック）
 * 3. AI 応答と提案テキストが表示される
 * 4. 「フォームに反映」→ フォームの職務要約が提案値に置き換わる（DB 更新なし = PUT は飛ばない）
 */

const baseResume = {
  id: "resume-1",
  full_name: "山田 太郎",
  email: "yamada@example.com",
  github_url: "",
  career_summary: "現在のサマリー",
  self_pr: "自己PR",
  experiences: [],
  qualifications: [],
};

async function setupResumeApi(page: Page) {
  await page.route("**/api/master-data/qualification", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/master-data/technology-stack", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/resumes/latest", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(baseResume),
    }),
  );
}

/** UserMenu → モデル選択モーダル経由で使用モデルを切り替える（ADR-0012）。 */
async function selectModel(page: Page, modelName: "Haiku" | "Sonnet") {
  await page.getByRole("button", { name: "e2e-test-user" }).click();
  await page.getByRole("button", { name: "AI モデルを切り替え" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByRole("button", { name: new RegExp(`^${modelName}`) }).click();
}

test.describe("Agent チャットウィジェット", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupResumeApi(page);
  });

  test("職務要約の改善提案を受け取りフォームに反映できる", async ({ page }) => {
    // Agent チャット API モック。送られた scope / resume を検証できるよう記録する
    let chatRequestBody: Record<string, unknown> | null = null;
    await page.route("**/api/agent/chat", async (route) => {
      chatRequestBody = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          message: "より具体的な職務要約を提案します。",
          operations: [{ field: "career_summary", value: "改善された職務要約です。" }],
        }),
      });
    });

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // ウィジェットを開く
    await page.getByRole("button", { name: "devforge Agent" }).click();

    // 職務要約スコープ（デフォルト）でプロンプト送信
    await page
      .getByPlaceholder("例: 成果がより伝わる文章にしてください")
      .fill("もっと具体的にして");
    await page.getByRole("button", { name: "送信", exact: true }).click();

    // AI 応答と提案テキストの表示
    await expect(page.getByText("より具体的な職務要約を提案します。")).toBeVisible();
    await expect(page.getByText("改善された職務要約です。")).toBeVisible();

    // リクエスト内容: スコープと編集中フォームのコンテキストが送られている
    expect(chatRequestBody).toMatchObject({
      scope: "career_summary",
      prompt: "もっと具体的にして",
      resume: { career_summary: "現在のサマリー" },
    });

    // フォームに反映 → 職務要約フィールドが提案値になる（state のみ。保存はしない）。
    // フォーム側のトリガーは先頭 N 文字 + … の省略プレビュー表示のため部分一致で検証する
    await page.getByRole("button", { name: "フォームに反映" }).click();
    await expect(page.getByRole("button", { name: "職務要約を編集" })).toContainText(
      "改善された職務要約で",
    );
    // 反映済みになると反映ボタンは消える
    await expect(page.getByRole("button", { name: "フォームに反映" })).toHaveCount(0);
  });

  test("使用モデルはサイドバーに表示され、UserMenu のモーダルで Sonnet に切り替えられる", async ({
    page,
  }) => {
    // サイドバーの残高（ADR-0012）。setupAuth のデフォルトより後に登録して上書きする
    await page.route("**/api/billing/balance", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ balance: 12000 }),
      }),
    );
    let chatRequestBody: Record<string, unknown> | null = null;
    await page.route("**/api/agent/chat", async (route) => {
      chatRequestBody = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "高精度モデルの提案です。", operations: [] }),
      });
    });

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    const sidebar = page.locator("aside").first();
    // 使用モデル・残高はサイドバーに常時表示される（既定は Haiku）
    await expect(sidebar.getByText("使用モデル")).toBeVisible();
    await expect(sidebar.getByText("Haiku")).toBeVisible();
    await expect(sidebar.getByText("クレジット残高")).toBeVisible();
    await expect(sidebar.getByText("12,000")).toBeVisible();

    // UserMenu → モデル選択モーダル → Sonnet カードで切り替え
    await selectModel(page, "Sonnet");
    await expect(sidebar.getByText("Sonnet")).toBeVisible();

    await page.getByRole("button", { name: "devforge Agent" }).click();
    await page
      .getByPlaceholder("例: 成果がより伝わる文章にしてください")
      .fill("プロらしい文章にして");
    await page.getByRole("button", { name: "送信", exact: true }).click();

    await expect(page.getByText("高精度モデルの提案です。")).toBeVisible();
    expect(chatRequestBody).toMatchObject({ model: "sonnet" });
  });

  test("Sonnet で残高不足（402）はエラートーストで通知される", async ({ page }) => {
    await page.route("**/api/agent/chat", (route) =>
      route.fulfill({
        status: 402,
        contentType: "application/json",
        body: JSON.stringify({
          code: "INSUFFICIENT_CREDITS",
          message:
            "クレジット残高が不足しています。Haiku（無料）に切り替えるか、クレジットを追加してください。",
        }),
      }),
    );

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // 残高 0（setupAuth の既定）で Sonnet に切り替えてから送信
    await selectModel(page, "Sonnet");
    await page.getByRole("button", { name: "devforge Agent" }).click();
    await page
      .getByPlaceholder("例: 成果がより伝わる文章にしてください")
      .fill("改善して");
    await page.getByRole("button", { name: "送信", exact: true }).click();

    await expect(
      page.getByText(
        "クレジット残高が不足しています。Haiku（無料）に切り替えるか、クレジットを追加してください。",
      ),
    ).toBeVisible();
  });

  test("LLM 失敗（502）はエラートーストで通知される", async ({ page }) => {
    await page.route("**/api/agent/chat", (route) =>
      route.fulfill({
        status: 502,
        contentType: "application/json",
        body: JSON.stringify({
          code: "AGENT_LLM_ERROR",
          message: "AI の応答取得に失敗しました。しばらくしてからもう一度お試しください。",
        }),
      }),
    );

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    await page.getByRole("button", { name: "devforge Agent" }).click();
    await page
      .getByPlaceholder("例: 成果がより伝わる文章にしてください")
      .fill("改善して");
    await page.getByRole("button", { name: "送信", exact: true }).click();

    await expect(
      page.getByText("AI の応答取得に失敗しました。しばらくしてからもう一度お試しください。"),
    ).toBeVisible();
  });
});
