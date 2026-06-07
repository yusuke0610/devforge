import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../../test/mswServer";
import { GitHubLinkDashboard } from "./GitHubLinkDashboard";
import { renderWithProviders } from "../../test/renderWithProviders";

/** Provider 付きでレンダリングするヘルパー（表示のみ） */
function renderPage() {
  return renderWithProviders(<GitHubLinkDashboard />);
}

/**
 * サイドバーから連携実行された状態（runNonce を含む location state）で描画する。
 * 連携 API のトリガーはサイドバークリックのみのため、テストでも state 経由で再現する。
 */
function renderPageWithRun(includeForks = false) {
  return renderWithProviders(<GitHubLinkDashboard />, {
    initialEntries: [
      {
        pathname: "/github_link",
        state: { runNonce: 1, includeForks },
      },
    ],
  });
}

/**
 * `GET /api/github-link/cache` をキャッシュ未保存（空状態）レスポンスに差し替える。
 */
function mockEmptyCache() {
  server.use(
    http.get("*/api/github-link/cache", () =>
      HttpResponse.json({
        result: null,
        status: null,
      }),
    ),
  );
}

describe("GitHubLinkDashboard", () => {
  it("キャッシュなしの場合、空状態メッセージが表示される", async () => {
    mockEmptyCache();

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/まだ連携データがありません/),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("GitHub連携")).toBeInTheDocument();
  });

  it("表示専用: ページ上に連携トリガーボタン（連携する/更新する/再連携）が無い", async () => {
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("test-user-001 の連携結果"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("連携する")).not.toBeInTheDocument();
    expect(screen.queryByText("更新する")).not.toBeInTheDocument();
    expect(screen.queryByText("再連携")).not.toBeInTheDocument();
  });

  it("キャッシュが存在する場合、結果画面が表示される", async () => {
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("test-user-001 の連携結果"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText("10")).toBeInTheDocument(); // repos_analyzed
    expect(screen.getByText("リポジトリ")).toBeInTheDocument();
  });

  it("コントリビューションカレンダーがあると Activity ヒートマップが最新年で表示される", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Activity")).toBeInTheDocument();
    });
    // 配列先頭（最新年=2025）がデフォルト表示される
    expect(screen.getByText("2025年のコントリビュート")).toBeInTheDocument();
    expect(screen.getByText("123")).toBeInTheDocument();
  });

  it("年セレクタで年を切り替えるとヒートマップの集計が切り替わる", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Activity")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox", { name: "表示する年" });
    await userEvent.selectOptions(select, "2024");

    expect(screen.getByText("2024年のコントリビュート")).toBeInTheDocument();
    expect(screen.getByText("88")).toBeInTheDocument();
  });

  it("コントリビューションカレンダーが空のとき Activity セクションが描画されない", async () => {
    server.use(
      http.get("*/api/github-link/cache", () =>
        HttpResponse.json({
          status: "completed",
          result: {
            username: "test-user-001",
            repos_analyzed: 1,
            unique_skills: 0,
            analyzed_at: "2026-01-01T00:00:00Z",
            languages: { TypeScript: 100 },
            contribution_calendars: [],
          },
        }),
      ),
    );

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("test-user-001 の連携結果"),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText("Activity")).not.toBeInTheDocument();
  });

  it("サイドバーからの連携実行(runNonce)でポーリング画面に遷移する", async () => {
    mockEmptyCache();
    server.use(
      http.get("*/api/github-link/cache/status", () =>
        HttpResponse.json({ status: "pending" }),
      ),
    );

    renderPageWithRun();

    await waitFor(() => {
      expect(
        screen.getByText("GitHubプロフィールを取得中..."),
      ).toBeInTheDocument();
    });
  });

  it("連携実行が 503 を返したときエラーメッセージが表示される", async () => {
    mockEmptyCache();
    server.use(
      http.post("*/api/github-link/run", () =>
        HttpResponse.json(
          {
            code: "INTERNAL_ERROR",
            message: "分析サービスが一時的に利用できません",
            error_id: "err-ui-500",
          },
          { status: 503 },
        ),
      ),
    );

    renderPageWithRun();

    await waitFor(() => {
      // エラーメッセージが表示されること（アプリがクラッシュしないこと）
      expect(
        screen.getByText(/分析サービスが一時的に利用できません/),
      ).toBeInTheDocument();
      expect(screen.getByText(/エラーID: err-ui-500/)).toBeInTheDocument();
    });
  });
});
