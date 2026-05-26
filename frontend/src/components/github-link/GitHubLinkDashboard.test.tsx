import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../../test/mswServer";
import { GitHubLinkDashboard } from "./GitHubLinkDashboard";
import { renderWithProviders } from "../../test/renderWithProviders";

/** Provider 付きでレンダリングするヘルパー */
function renderPage() {
  return renderWithProviders(<GitHubLinkDashboard />);
}

/**
 * `GET /api/github-link/cache` をキャッシュ未保存（入力画面表示）レスポンスに差し替える。
 * 2 箇所でコピペされていた server.use ブロックを集約する。
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
  it("キャッシュなしの場合、入力画面が表示される", async () => {
    mockEmptyCache();

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("連携開始")).toBeInTheDocument();
    });
    expect(screen.getByText("GitHub連携")).toBeInTheDocument();
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

  it("連携開始ボタン押下後、ポーリング画面に遷移する", async () => {
    const user = userEvent.setup();

    mockEmptyCache();
    server.use(
      http.get("*/api/github-link/cache/status", () =>
        HttpResponse.json({ status: "pending" }),
      ),
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("連携開始")).toBeInTheDocument();
    });

    await user.click(screen.getByText("連携開始"));

    await waitFor(() => {
      expect(
        screen.getByText("GitHubプロフィールを取得中..."),
      ).toBeInTheDocument();
    });
  });

  it("API 500 エラー時にエラーメッセージが表示される", async () => {
    const user = userEvent.setup();

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

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("連携開始")).toBeInTheDocument();
    });

    await user.click(screen.getByText("連携開始"));

    await waitFor(() => {
      // エラーメッセージが表示されること（アプリがクラッシュしないこと）
      expect(screen.getByText(/AI 分析サービスが一時的に利用できません/)).toBeInTheDocument();
      expect(screen.getByText(/エラーID: err-ui-500/)).toBeInTheDocument();
    });
  });

  it("再連携ボタンで入力画面に戻る", async () => {
    const user = userEvent.setup();

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("test-user-001 の連携結果"),
      ).toBeInTheDocument();
    });

    await user.click(screen.getByText("再連携"));

    await waitFor(() => {
      expect(screen.getByText("連携開始")).toBeInTheDocument();
    });
  });
});
