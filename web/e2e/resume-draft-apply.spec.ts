import { expect, test, type Page } from "@playwright/test";

import {
  RESUME_DRAFT_CANDIDATE_MESSAGES,
  RESUME_DRAFT_MESSAGES,
} from "../src/constants/messages";
import { setupAuth, waitForAuthenticatedLayout } from "./helpers/auth";

/**
 * 経歴書ドラフトの候補選択 → 生成 → フォーム追加の E2E（ADR-0026 決定 2 / 5 / #565・#566）。
 *
 * シナリオ:
 * 1. GitHub 連携済みユーザに候補一覧が出る（デフォルト非選択のものは理由バッジ付きで残る）
 * 2. 採用リポジトリを選んでドラフトを生成（enqueue→完了→PDF プレビュー）
 * 3. 「この内容をフォームに反映」で /career へ遷移し、追加先を選んで案件を**追加**する
 * 4. 既存の職歴は置き換わらない（追加のみ）
 */

async function setupDraftAndCareer(page: Page) {
  await page.route("**/api/github-link/cache", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "completed",
        result: {
          username: "e2e-test-user",
          repos_analyzed: 2,
          unique_skills: 1,
          analyzed_at: "2026-04-24T00:00:00Z",
          languages: { TypeScript: 100 },
        },
      }),
    }),
  );
  await page.route("**/api/github-link/skills", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ skills: [] }) }),
  );
  // 候補一覧（機械は候補を落とさず、ノイズはデフォルト非選択 + 理由で表現する）
  await page.route("**/api/agent/resume-draft/candidates", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        selection_limit: 5,
        candidates: [
          {
            full_name: "e2e-test-user/devforge",
            description: "経歴書作成ツール",
            duration_days: 420,
            implementation_volume: 120000,
            has_infra: true,
            technology_stacks: [{ category: "language", name: "TypeScript" }],
            default_selected: true,
            reasons: [],
          },
          {
            full_name: "e2e-test-user/tutorial",
            description: "写経",
            duration_days: 2,
            implementation_volume: 300,
            has_infra: false,
            technology_stacks: [],
            default_selected: false,
            reasons: ["short_duration", "learning_topic"],
          },
        ],
      }),
    }),
  );
  // ドラフト生成フロー（enqueue→完了→PDF）
  await page.route("**/api/agent/resume-draft/status", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "completed" }) }),
  );
  await page.route("**/api/agent/resume-draft/run", (route) =>
    route.fulfill({ status: 202, contentType: "application/json", body: JSON.stringify({ status: "pending" }) }),
  );
  await page.route("**/api/agent/resume-draft/pdf", (route) =>
    route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n%mock\n" }),
  );
  // payload 取得（フォーム追加用）。出力単位はプロジェクト明細のリスト（ADR-0026 決定 1）
  await page.route("**/api/agent/resume-draft/result", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        full_name: "ドラフト 太郎",
        email: "",
        github_url: "https://github.com/e2e-test-user",
        career_summary: "GitHub から生成した職務要約。",
        self_pr: "生成した自己PR。",
        projects: [
          {
            name: "devforge",
            description: "経歴書作成ツールを個人開発した。",
            role: "",
            phases: [],
            periods: [{ start_date: "2024-01", end_date: "", is_current: true }],
            team: { total: "", members: [] },
            technology_stacks: [{ category: "language", name: "TypeScript" }],
          },
        ],
      }),
    }),
  );
  // /career 側: 保存済み経歴書なし（空フォーム）+ マスタ空
  await page.route("**/api/resumes/latest", (route) =>
    route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ code: "NOT_FOUND", message: "not found" }) }),
  );
  await page.route("**/api/master-data/qualification", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/master-data/technology-stack", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}

test.describe("ドラフトの候補選択とフォーム追加", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page);
    await setupDraftAndCareer(page);
  });

  test("候補を選んで生成し、追加先を指定して案件をフォームへ追加できる", async ({ page }) => {
    await page.goto("/github_link");
    await waitForAuthenticatedLayout(page);

    // 候補は全件出る。ノイズはデフォルト非選択で理由バッジが付く（落とさない）
    await expect(page.getByText("e2e-test-user/devforge")).toBeVisible();
    await expect(page.getByText("e2e-test-user/tutorial")).toBeVisible();
    await expect(
      page.getByText(RESUME_DRAFT_CANDIDATE_MESSAGES.REASON_LABELS.learning_topic),
    ).toBeVisible();

    // デフォルト選択済みの 1 件でそのまま生成 → PDF プレビューが開く
    await page.getByRole("button", { name: RESUME_DRAFT_MESSAGES.GENERATE }).click();
    await expect(page.getByText("PDFプレビュー")).toBeVisible();

    // 「この内容をフォームに反映」→ /career へ遷移し、追加ダイアログが開く
    await page.getByRole("button", { name: RESUME_DRAFT_MESSAGES.APPLY_TO_FORM }).click();
    await expect(page).toHaveURL(/\/career$/);
    await expect(
      page.getByRole("heading", { name: RESUME_DRAFT_MESSAGES.INJECT_HEADING }),
    ).toBeVisible();

    // 追加先（職歴・取引先）を選んで追加する
    await page.getByRole("button", { name: RESUME_DRAFT_MESSAGES.INJECT_SUBMIT }).click();

    await expect(page.getByText(RESUME_DRAFT_MESSAGES.APPLIED_TOAST)).toBeVisible();
    // 案件として追加される（氏名などは上書きされない）
    await expect(page.getByText("devforge", { exact: true })).toBeVisible();
    await expect(page.getByPlaceholder("例: 山田 太郎")).toHaveValue("");
  });
});
