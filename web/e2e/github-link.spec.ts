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
    // スキルセクション（D11）がマウント時に叩く一覧 API。空で返す
    await page.route("**/api/github-link/skills", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ skills: [] }),
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

  test("連携後の「ドラフト生成」ボタンで非同期生成が走りプレビューが開く", async ({
    page,
  }) => {
    // 連携済み（result あり）→ ダッシュボードにドラフト生成セクションが出る
    await page.route("**/api/github-link/cache", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "completed",
          result: {
            username: "e2e-test-user",
            repos_analyzed: 1,
            unique_skills: 1,
            analyzed_at: "2026-04-24T00:00:00Z",
            languages: { TypeScript: 100 },
            repos: [
              {
                full_name: "e2e-test-user/app",
                description: "アプリ",
                created_at: "2024-01-01T00:00:00Z",
                pushed_at: "2026-04-01T00:00:00Z",
              },
            ],
          },
        }),
      }),
    );
    // マウント時・ポーリングとも完了を返す（enqueue → 即完了 → PDF 取得の順で流れる）
    await page.route("**/api/agent/resume-draft/status", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "completed" }),
      }),
    );
    let runCalled = false;
    await page.route("**/api/agent/resume-draft/run", (route) => {
      runCalled = true;
      return route.fulfill({
        status: 202,
        contentType: "application/json",
        body: JSON.stringify({ status: "pending" }),
      });
    });
    await page.route("**/api/agent/resume-draft/pdf", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/pdf",
        body: "%PDF-1.4\n%mock\n",
      }),
    );
    await page.route("**/api/github-link/skills", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ skills: [] }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    // 連携結果が表示され、ドラフト生成ボタンが出る
    await expect(
      page.getByRole("heading", { name: "e2e-test-user の連携結果" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "経歴書ドラフトPDFを生成" })
      .click();

    // enqueue → ポーリング完了 → PDF 取得でプレビューモーダルが開く
    await expect(page.getByText("PDFプレビュー")).toBeVisible();
    expect(runCalled).toBe(true);
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

  test("スキル表示名を AI 提案 → 確定するとチップに確定表示名が反映される（D11）", async ({
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
            unique_skills: 1,
            analyzed_at: "2026-04-24T00:00:00Z",
            languages: { TypeScript: 100 },
          },
        }),
      }),
    );
    // 初期一覧: 未確定の package 1 件（canonical 名で表示される）
    await page.route("**/api/github-link/skills", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          skills: [
            {
              kind: "package",
              canonical_name: "@aws-sdk/client-s3",
              ecosystem: "npm",
              parent: null,
              display_name: null,
              confirmed_display_name: null,
              group_id: null,
              decision_source: null,
              decision_reviewed: false,
              evidence: [],
              proficiency: null,
            },
          ],
        }),
      }),
    );
    await page.route("**/api/github-link/skills/display-names/propose", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          groups: [
            {
              display_name: "Amazon S3",
              members: [
                { kind: "package", ecosystem: "npm", canonical_name: "@aws-sdk/client-s3" },
              ],
            },
          ],
        }),
      }),
    );
    // 確定後の一覧: confirmed_display_name が入った状態を返す
    await page.route("**/api/github-link/skills/display-decisions", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          skills: [
            {
              kind: "package",
              canonical_name: "@aws-sdk/client-s3",
              ecosystem: "npm",
              parent: null,
              display_name: null,
              confirmed_display_name: "Amazon S3",
              group_id: null,
              decision_source: "agent",
              decision_reviewed: true,
              evidence: [],
              proficiency: null,
            },
          ],
        }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    // 未確定なので canonical 名がチップに出る
    await expect(page.getByText("@aws-sdk/client-s3")).toBeVisible();

    // 提案 → レビューパネルが開く
    await page.getByRole("button", { name: "表示名をAIに提案してもらう" }).click();
    await expect(
      page.getByText("表示名の提案（確認して確定してください）"),
    ).toBeVisible();
    await expect(page.getByRole("textbox", { name: "表示名" })).toHaveValue(
      "Amazon S3",
    );

    // 確定 → チップに確定表示名が反映される
    await page.getByRole("button", { name: "この内容で確定" }).click();
    await expect(page.getByText("Amazon S3")).toBeVisible();
  });

  test("確定済みスキルの「解除」で機械デフォルト（canonical 名）に戻る（D11 / #496）", async ({
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
            unique_skills: 1,
            analyzed_at: "2026-04-24T00:00:00Z",
            languages: { TypeScript: 100 },
          },
        }),
      }),
    );
    // 初期一覧: 確定済み（confirmed_display_name あり）→ チップに確定名と「解除」が出る
    await page.route("**/api/github-link/skills", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          skills: [
            {
              kind: "package",
              canonical_name: "@aws-sdk/client-s3",
              ecosystem: "npm",
              parent: null,
              display_name: null,
              confirmed_display_name: "Amazon S3",
              group_id: null,
              decision_source: "human",
              decision_reviewed: true,
              evidence: [],
              proficiency: null,
            },
          ],
        }),
      }),
    );
    // 解除（DELETE）後の一覧: confirmed_display_name が null に戻る
    await page.route("**/api/github-link/skills/display-decisions", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          skills: [
            {
              kind: "package",
              canonical_name: "@aws-sdk/client-s3",
              ecosystem: "npm",
              parent: null,
              display_name: null,
              confirmed_display_name: null,
              group_id: null,
              decision_source: null,
              decision_reviewed: false,
              evidence: [],
              proficiency: null,
            },
          ],
        }),
      }),
    );

    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    // 確定済みなので確定表示名がチップに出る
    await expect(page.getByText("Amazon S3")).toBeVisible();

    // 「解除」→ 機械デフォルト（canonical 名）に戻る
    await page
      .getByRole("button", { name: "Amazon S3 の表示名確定を解除" })
      .click();
    await expect(page.getByText("@aws-sdk/client-s3")).toBeVisible();
    await expect(page.getByText("Amazon S3")).toHaveCount(0);
  });
});
