import { test, expect, type Locator, type Page } from "@playwright/test";

import { IMPORT_ASSIST_MESSAGES } from "../src/constants/messages";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 職務経歴書のファイル取り込み補助（原本ビュー）E2E。
 *
 * 取り込み導線は右カラムの原本ビューに一本化されており、ドラッグ&ドロップ / クリック選択で
 * PDF・Markdown を読み込む。ここでは Markdown の描画と、種別・サイズのエラーパターンを検証する。
 *
 * シナリオ:
 * 1. Markdown をファイル選択で読み込む → 原本が整形描画される
 * 2. Markdown をドラッグ&ドロップで読み込む → 原本が整形描画される
 * 3. 原本上で選択した文字が、フォーカス中の入力欄へ流し込まれる
 * 4. 拡張子が pdf/md 以外（.txt）→ 未対応エラーを表示し描画しない
 * 5. サイズ上限超過の Markdown → サイズ超過エラーを表示し描画しない
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
        career_summary: "サマリー",
        self_pr: "自己PR",
        experiences: [],
        qualifications: [],
      }),
    }),
  );
}

/** 原本ビュー内の隠しファイル input（aria-label で一意）。 */
function importInput(page: Page): Locator {
  return page.locator(`input[aria-label="${IMPORT_ASSIST_MESSAGES.SELECT_FILE}"]`);
}

/** 描画された Markdown 原本の本文要素。 */
function markdownBody(page: Page): Locator {
  return page.locator("[class*='markdownBody']");
}

const SAMPLE_MD = "# E2Eマークダウン見出し\n\n- 取り込みテスト項目\n";

test.describe("職務経歴書 ファイル取り込み補助", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupResumeApi(page);
    await page.goto("/career");
    await waitForAuthenticatedLayout(page);
  });

  test("ファイル選択で Markdown を読み込むと原本が整形描画される", async ({ page }) => {
    await importInput(page).setInputFiles({
      name: "resume.md",
      mimeType: "text/markdown",
      buffer: Buffer.from(SAMPLE_MD, "utf-8"),
    });

    // 見出し（h1）とリスト項目が原本ビュー内に描画される
    await expect(markdownBody(page).getByText("E2Eマークダウン見出し")).toBeVisible();
    await expect(markdownBody(page).getByText("取り込みテスト項目")).toBeVisible();
    // タブにファイル名が出る
    await expect(page.getByText("resume.md")).toBeVisible();
  });

  test("Markdown をドラッグ&ドロップで読み込むと原本が整形描画される", async ({ page }) => {
    // ファイルを載せた DataTransfer を生成し、ドロップゾーンへ drop イベントを発火する。
    const dataTransfer = await page.evaluateHandle((content) => {
      const dt = new DataTransfer();
      dt.items.add(new File([content], "dropped.md", { type: "text/markdown" }));
      return dt;
    }, SAMPLE_MD);

    const dropzone = page.locator("[class*='dropzone']");
    await dropzone.dispatchEvent("dragover", { dataTransfer });
    await dropzone.dispatchEvent("drop", { dataTransfer });

    await expect(markdownBody(page).getByText("E2Eマークダウン見出し")).toBeVisible();
    await expect(page.getByText("dropped.md")).toBeVisible();
  });

  test("原本上で選択した文字がフォーカス中の入力欄のカーソル位置へ挿入される", async ({ page }) => {
    await importInput(page).setInputFiles({
      name: "resume.md",
      mimeType: "text/markdown",
      buffer: Buffer.from(SAMPLE_MD, "utf-8"),
    });
    await expect(markdownBody(page).getByText("取り込みテスト項目")).toBeVisible();

    // 流し込み先として氏名欄（モックで "山田 太郎" がロード済み）をフォーカスする
    // （focusin で「最後にフォーカスした入力欄」に記録される）。
    const nameInput = page.getByPlaceholder("例: 山田 太郎");
    await nameInput.click();

    // 原本のリスト項目テキストを選択し、mouseup を発火して流し込む
    await page.evaluate(() => {
      const body = document.querySelector("[class*='markdownBody']");
      const target = body?.querySelector("li") ?? body;
      if (!target) throw new Error("markdown body not found");
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
      target.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    });

    // 既存値 "山田 太郎" を置換せず、カーソル位置へ挿入される（旧仕様では全置換され
    // "取り込みテスト項目" だけになっていた）。このプログラム的な選択操作では caret が
    // 先頭に戻るため先頭挿入になるが、検証の主眼は「既存値が保持されること」。
    // カーソル位置挿入そのものの精緻な検証はユニットテスト側が担う。
    await expect(nameInput).toHaveValue("取り込みテスト項目山田 太郎");
  });

  test("拡張子が pdf/md 以外（.txt）だと未対応エラーを表示し描画しない", async ({ page }) => {
    await importInput(page).setInputFiles({
      name: "note.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("ただのテキスト", "utf-8"),
    });

    await expect(page.getByText(IMPORT_ASSIST_MESSAGES.UNSUPPORTED_TYPE)).toBeVisible();
    // 原本は描画されず、ドロップゾーンが残る
    await expect(markdownBody(page)).toHaveCount(0);
    await expect(page.getByText(IMPORT_ASSIST_MESSAGES.DROPZONE)).toBeVisible();
  });

  test("サイズ上限を超える Markdown はサイズ超過エラーを表示し描画しない", async ({ page }) => {
    // Markdown 上限は 2MB。3MB のダミーを渡して弾かれることを確認する。
    await importInput(page).setInputFiles({
      name: "huge.md",
      mimeType: "text/markdown",
      buffer: Buffer.alloc(3 * 1024 * 1024, 0x61),
    });

    await expect(page.getByText(IMPORT_ASSIST_MESSAGES.TOO_LARGE(2))).toBeVisible();
    await expect(markdownBody(page)).toHaveCount(0);
    await expect(page.getByText(IMPORT_ASSIST_MESSAGES.DROPZONE)).toBeVisible();
  });
});
