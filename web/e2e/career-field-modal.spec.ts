import { test, expect, type Page } from "@playwright/test";

import { UI_MESSAGES, charCountLabel } from "../src/constants/messages";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 自己PR・職務要約の専用入力モーダル E2E。
 *
 * これらのフィールドはフォーム本体ではプレビュー + 編集ボタンに集約され、入力は専用モーダルで行う。
 * シナリオ:
 * 1. 「自己PRを編集」ボタンでモーダルが開き、現在値が入力欄に出る
 * 2. 入力すると右下の文字数カウント（空白除外）が更新される
 * 3. × で閉じると、入力値がフォーム側プレビューに反映されている
 */

/** 職務経歴書の最小 API モック（マスタ・最新取得）。 */
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
      body: JSON.stringify({
        id: "resume-1",
        full_name: "山田 太郎",
        email: "yamada@example.com",
        github_url: "",
        career_summary: "初期サマリー",
        self_pr: "初期自己PR",
        experiences: [],
        qualifications: [],
      }),
    }),
  );
}

test.describe("職務経歴書 自己PR・職務要約モーダル", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupResumeApi(page);
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);
  });

  test("自己PRをモーダルで編集すると文字数カウントが更新されフォームへ反映される", async ({
    page,
  }) => {
    // フォーム本体には現在値のプレビューが出ている。
    await expect(page.getByText("初期自己PR")).toBeVisible();

    // 「自己PRを編集」ボタンでモーダルを開く。
    await page
      .getByRole("button", { name: `${UI_MESSAGES.FIELD_SELF_PR}を${UI_MESSAGES.EDIT}` })
      .click();

    // モーダル内の入力欄（textarea は本フォームではモーダル内にのみ存在）に現在値がロードされている。
    const textarea = page.locator("textarea");
    await expect(textarea).toHaveValue("初期自己PR");

    // 入力すると右下の文字数カウント（空白除外）が更新される。
    await textarea.fill("新しい 自己PR 本文");
    // 空白を除くと「新しい自己PR本文」= 9 文字（新・し・い・自・己・P・R・本・文）。
    await expect(page.getByText(charCountLabel(9), { exact: true })).toBeVisible();

    // × で閉じる。
    await page.getByRole("button", { name: UI_MESSAGES.MODAL_CLOSE, exact: true }).click();
    await expect(textarea).toHaveCount(0);

    // フォーム側プレビューに編集値が反映されている（即時に formCache へ反映）。
    // プレビューは Markdown 記法除去後の先頭10文字まで（超過分は省略記号）。
    await expect(page.getByText("新しい 自己PR 本…", { exact: true })).toBeVisible();
  });

  test("必須未入力で保存すると職務要約モーダルが自動で開く", async ({ page }) => {
    // 職務要約を空にするため、まずモーダルを開いて全消しする。
    await page
      .getByRole("button", {
        name: `${UI_MESSAGES.FIELD_CAREER_SUMMARY}を${UI_MESSAGES.EDIT}`,
      })
      .click();
    const textarea = page.locator("textarea");
    await textarea.fill("");
    await page.getByRole("button", { name: UI_MESSAGES.MODAL_CLOSE, exact: true }).click();
    await expect(textarea).toHaveCount(0);

    // 保存（更新）ボタンを押すと、職務要約が未入力なのでモーダルが自動で開く。
    await page.getByRole("button", { name: /更新する|保存する/ }).click();
    // 開いたのが職務要約モーダルであることをタイトル（完全一致）で確認する。
    await expect(page.getByText(UI_MESSAGES.FIELD_CAREER_SUMMARY, { exact: true })).toBeVisible();
  });
});
