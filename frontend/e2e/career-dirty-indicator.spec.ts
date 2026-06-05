import { test, expect, type Page } from "@playwright/test";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 職務経歴書の未保存マーク（🔴）E2E。
 *
 * シナリオ:
 * 1. 職務経歴書を開く → 🔴 なし
 * 2. 氏名を編集 → 氏名横と保存ボタン横に 🔴
 * 3. ブログ連携タブへ遷移して職務経歴書に戻る → 🔴 が維持されている（Redux 保持）
 * 4. 保存（PUT /api/resumes/{id}）→ baseline 更新で 🔴 が全消失
 */

/** 職務経歴書の API モックをまとめてセットする */
async function setupResumeApi(page: Page) {
  const baseResume = {
    id: "resume-1",
    full_name: "山田 太郎",
    career_summary: "サマリー",
    self_pr: "自己PR",
    experiences: [
      {
        company: "株式会社A",
        business_description: "受託開発",
        start_date: "2020-04",
        end_date: null,
        is_current: true,
        employee_count: "100",
        capital: "1",
        clients: [],
      },
    ],
    qualifications: [],
  };

  // マスタデータ
  await page.route("**/api/master-data/qualification", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/master-data/technology-stack", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );

  // 保存前プレビュー（左右 diff モーダル）。整形 HTML と CSS を返す。
  await page.route("**/api/resumes/preview", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        html: '<div class="meta">氏名　<span data-fp="full_name">山田 太郎</span></div>',
        css: "",
      }),
    }),
  );

  // 最新取得
  await page.route("**/api/resumes/latest", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(baseResume),
    }),
  );

  // 更新（PUT）。レスポンスは編集後の値で返す前提だが、テストでは保存後 🔴 が消えれば良いので
  // request 内容をそのまま baseline として返す。
  await page.route("**/api/resumes/resume-1", async (route) => {
    if (route.request().method() === "PUT") {
      const body = JSON.parse(route.request().postData() ?? "{}");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...baseResume, ...body }),
      });
      return;
    }
    await route.fallback();
  });

  // ブログ連携ページ用モック（タブ遷移先で連携アカウント空を返す）
  await page.route("**/api/blog/accounts", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}

test.describe("職務経歴書 未保存マーク", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupResumeApi(page);
  });

  test("ProjectModal 内でフィールドを編集すると該当ラベル横に 🔴 が出る", async ({ page }) => {
    // baseResume を上書きして 1 件のプロジェクトを持たせる
    const baseResumeWithProject = {
      id: "resume-1",
      full_name: "山田 太郎",
      career_summary: "サマリー",
      self_pr: "自己PR",
      experiences: [
        {
          company: "株式会社A",
          business_description: "受託開発",
          start_date: "2020-04",
          end_date: null,
          is_current: true,
          employee_count: "100",
          capital: "1",
          clients: [
            {
              name: "クライアントA",
              has_client: true,
              projects: [
                {
                  name: "既存プロジェクト",
                  start_date: "2021-04",
                  end_date: "2022-03",
                  is_current: false,
                  role: "Eng",
                  description: "",
                  team: { total: "5", members: [] },
                  technology_stacks: [],
                  phases: [],
                },
              ],
            },
          ],
        },
      ],
      qualifications: [],
    };
    await page.unroute("**/api/resumes/latest");
    await page.route("**/api/resumes/latest", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(baseResumeWithProject),
      }),
    );

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // 初期状態: dirty なし
    await expect(page.getByTestId("dirty-dot")).toHaveCount(0);

    // プロジェクト「編集」ボタンを押す
    await page.getByRole("button", { name: "編集" }).click();

    // モーダル内のプロジェクト名を変更
    const projectNameInput = page.getByPlaceholder("例: エネルギー業界 IoT Web API アプリ新規開発");
    await projectNameInput.fill("既存プロジェクト改");

    // モーダル内で 🔴 が表示される（タイトル横とプロジェクト名ラベル横）
    await expect(page.getByTestId("dirty-dot").first()).toBeVisible();
    const dotCount = await page.getByTestId("dirty-dot").count();
    expect(dotCount).toBeGreaterThanOrEqual(2);
  });

  test("新規ユーザー（DB データなし）で氏名を編集すると 🔴 が表示される", async ({ page }) => {
    // 初回ログインで職務経歴データがないユーザー（loadLatest が 404）を再現
    await page.unroute("**/api/resumes/latest");
    await page.route("**/api/resumes/latest", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ code: "NOT_FOUND", message: "not found" }),
      }),
    );

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // 初期状態: baseline が初期空フォームに確定するため、編集前は 🔴 なし
    await expect(page.getByTestId("dirty-dot")).toHaveCount(0);

    // 氏名を入力 → 初期空フォーム ("") と比較して dirty に
    await page.getByPlaceholder("例: 山田 太郎").fill("テスト 太郎");
    await expect(page.getByTestId("dirty-dot").first()).toBeVisible();
  });

  test("新規ユーザー（DB データなし）でフォーム編集しても React の setState 警告が出ない", async ({
    page,
  }) => {
    // /api/resumes/latest を 404 にして「初回ログインで職務経歴データがないユーザー」を再現する
    await page.unroute("**/api/resumes/latest");
    await page.route("**/api/resumes/latest", (route) =>
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ code: "NOT_FOUND", message: "not found" }),
      }),
    );

    // コンソール警告/エラーを収集する
    const consoleIssues: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "warning" || msg.type() === "error") {
        consoleIssues.push(`[${msg.type()}] ${msg.text()}`);
      }
    });

    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // 何文字か入力して setForm を複数回トリガーする
    const nameInput = page.getByPlaceholder("例: 山田 太郎");
    await nameInput.fill("テスト 太郎");

    // microtask の dispatch が消化されるまで少し待つ
    await page.waitForTimeout(100);

    // 「Cannot update a component while rendering a different component」警告が無いこと
    const setStateWarnings = consoleIssues.filter((m) => m.includes("Cannot update a component"));
    expect(setStateWarnings, setStateWarnings.join("\n")).toEqual([]);
  });

  test("編集 → 🔴 表示 → タブ遷移後も維持 → 保存で消える", async ({ page }) => {
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);

    // 1. 初期状態: 🔴 は出ていない
    await expect(page.getByTestId("dirty-dot")).toHaveCount(0);

    // 2. 氏名を編集
    const nameInput = page.getByPlaceholder("例: 山田 太郎");
    await nameInput.fill("佐藤 花子");

    // 🔴 が氏名 label 横に現れる
    await expect(page.getByTestId("dirty-dot").first()).toBeVisible();
    const dirtyCountAfterEdit = await page.getByTestId("dirty-dot").count();
    expect(dirtyCountAfterEdit).toBeGreaterThanOrEqual(1);

    // 3. ブログ連携タブへ遷移
    await page.getByRole("link", { name: "ブログ連携" }).click();
    await expect(page).toHaveURL(/\/blog/);

    // 職務経歴書に戻る
    await page.getByRole("link", { name: "職務経歴書" }).click();
    await expect(page).toHaveURL(/\/career$/);
    await waitForAuthenticatedLayout(page);

    // 編集値と 🔴 が維持されている
    await expect(nameInput).toHaveValue("佐藤 花子");
    const dirtyCountAfterReturn = await page.getByTestId("dirty-dot").count();
    expect(dirtyCountAfterReturn).toBeGreaterThanOrEqual(1);

    // 4. 保存ボタン → 変更点 diff モーダルが開く → 「この内容で保存」で確定 → 🔴 が全消失
    await page.getByRole("button", { name: /更新する|保存する/ }).click();
    await page.getByRole("button", { name: "この内容で保存" }).click();
    await expect(page.getByTestId("dirty-dot")).toHaveCount(0);
  });
});
