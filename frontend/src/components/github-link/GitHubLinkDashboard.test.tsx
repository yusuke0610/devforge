import { screen, waitFor } from "@testing-library/react";
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

  it("コントリビューションカレンダーがあると Activity ヒートマップが表示される", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Activity")).toBeInTheDocument();
    });
    expect(screen.getByText("年間コントリビュート")).toBeInTheDocument();
    expect(screen.getByText("123")).toBeInTheDocument();
  });

  it("検出フレームワークがあるとき Frameworks セクションにバーが表示される", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Frameworks")).toBeInTheDocument();
    });
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("FastAPI")).toBeInTheDocument();
  });

  it("DevTools があるとき DevTools セクションが表示される", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("DevTools")).toBeInTheDocument();
    });
    expect(screen.getByText("Docker")).toBeInTheDocument();
    expect(screen.getByText("GitHub Actions")).toBeInTheDocument();
  });

  it("Infra があるとき Infra セクションが表示される", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Infra")).toBeInTheDocument();
    });
    expect(screen.getByText("Terraform")).toBeInTheDocument();
  });

  it("検出フレームワークが空のとき Frameworks セクションが描画されない", async () => {
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
            detected_frameworks: {},
            detected_devtools: {},
            detected_infras: {},
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
    expect(screen.queryByText("Frameworks")).not.toBeInTheDocument();
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
            code: "LLM_UNAVAILABLE",
            message: "AI 分析サービスが一時的に利用できません",
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
        screen.getByText(/AI 分析サービスが一時的に利用できません/),
      ).toBeInTheDocument();
      expect(screen.getByText(/エラーID: err-ui-500/)).toBeInTheDocument();
    });
  });
});
