import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { request } from "./client";
import { ApiError } from "../utils/appError";

/** fetch のモックレスポンスを生成するヘルパー */
function makeResponse(status: number, body?: unknown): Response {
  const bodyStr = body !== undefined ? JSON.stringify(body) : "";
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
    text: vi.fn().mockResolvedValue(bodyStr),
    headers: new Headers(),
  } as unknown as Response;
}

describe("api/client request", () => {
  beforeEach(() => {
    // document.cookie をリセット
    Object.defineProperty(document, "cookie", {
      writable: true,
      value: "",
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  /** 200 レスポンスの場合、JSON がパースされて返されること */
  it("200 レスポンスの場合 JSON が返される", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(makeResponse(200, { id: "abc" })));

    const result = await request<{ id: string }>("/api/test");
    expect(result).toEqual({ id: "abc" });
  });

  /** 401 レスポンス → リフレッシュ成功 → リトライが成功すること */
  it("401 レスポンス後にリフレッシュが成功するとリトライされる", async () => {
    const fetchMock = vi
      .fn()
      // 1回目: 401（元リクエスト）
      .mockResolvedValueOnce(makeResponse(401))
      // 2回目: /auth/refresh → 200
      .mockResolvedValueOnce(makeResponse(200, {}))
      // 3回目: リトライ → 200
      .mockResolvedValueOnce(makeResponse(200, { id: "retried" }));

    vi.stubGlobal("fetch", fetchMock);

    const result = await request<{ id: string }>("/api/test");

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(result).toEqual({ id: "retried" });
  });

  /** 401 → リフレッシュ失敗 → エラーがスローされること */
  it("401 後にリフレッシュが失敗するとエラーがスローされる", async () => {
    const fetchMock = vi
      .fn()
      // 1回目: 元リクエスト 401
      .mockResolvedValueOnce(makeResponse(401))
      // 2回目: /auth/refresh 失敗
      .mockResolvedValueOnce(makeResponse(401));

    vi.stubGlobal("fetch", fetchMock);

    await expect(request("/api/test")).rejects.toThrow("認証が必要です");
  });

  /** 複数の同時 401 が来ても、同じ refresh を待って両方リトライされること */
  it("複数の同時 401 は 1 回のリフレッシュを共有して両方成功する", async () => {
    let refreshCallCount = 0;
    const attempts = new Map<string, number>();
    let resolveRefresh!: (response: Response) => void;
    const refreshPromise = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });

    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if ((url as string).includes("/auth/refresh")) {
        refreshCallCount++;
        return refreshPromise;
      }

      const attempt = attempts.get(url) ?? 0;
      attempts.set(url, attempt + 1);
      if (attempt === 0) {
        return Promise.resolve(makeResponse(401));
      }
      return Promise.resolve(makeResponse(200, { id: new URL(url, "http://localhost").pathname }));
    });

    vi.stubGlobal("fetch", fetchMock);

    const req1 = request<{ id: string }>("/api/test1");
    const req2 = request<{ id: string }>("/api/test2");

    await Promise.resolve();
    expect(refreshCallCount).toBe(1);

    resolveRefresh(makeResponse(200, {}));

    await expect(req1).resolves.toEqual({ id: "/api/test1" });
    await expect(req2).resolves.toEqual({ id: "/api/test2" });
    expect(refreshCallCount).toBe(1);
  });

  /** 並行 401 でリフレッシュが失敗した場合、両方の元リクエストがエラーで rejected になること */
  it("複数の同時 401 はリフレッシュ失敗時に 1 回のリフレッシュを共有して両方失敗する", async () => {
    let refreshCallCount = 0;
    let resolveRefresh!: (response: Response) => void;
    const refreshPromise = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });

    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if ((url as string).includes("/auth/refresh")) {
        refreshCallCount++;
        return refreshPromise;
      }
      return Promise.resolve(makeResponse(401));
    });

    vi.stubGlobal("fetch", fetchMock);

    const req1 = request("/api/test1");
    const req2 = request("/api/test2");

    await Promise.resolve();
    expect(refreshCallCount).toBe(1);

    resolveRefresh(makeResponse(401));

    await expect(req1).rejects.toThrow("認証が必要です");
    await expect(req2).rejects.toThrow("認証が必要です");
    expect(refreshCallCount).toBe(1);
  });

  /** 500 系のレスポンスでエラーがスローされること */
  it("500 レスポンスの場合エラーがスローされる", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(makeResponse(500)));

    await expect(request("/api/test")).rejects.toThrow("予期しないエラーが発生しました");
  });

  it("構造化エラーレスポンスの場合 code と errorId を保持する", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        makeResponse(503, {
          code: "LLM_UNAVAILABLE",
          message: "AI 分析サービスが一時的に利用できません",
          action: "しばらく待ってから再試行してください",
          error_id: "err-1234",
        }),
      ),
    );

    await expect(request("/api/test")).rejects.toMatchObject({
      code: "LLM_UNAVAILABLE",
      message: "AI 分析サービスが一時的に利用できません",
      errorId: "err-1234",
    } satisfies Partial<ApiError>);
  });

  /** 503 の detail があれば汎用文言ではなく detail を返すこと */
  it("503 レスポンスで detail があれば detail が優先される", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        makeResponse(503, {
          detail: "AI キャリアパス分析サービスが利用できません。LLM の設定または接続状態を確認してください。",
        }),
      ),
    );

    await expect(request("/api/test")).rejects.toThrow(
      "AI キャリアパス分析サービスが利用できません。LLM の設定または接続状態を確認してください。",
    );
  });

  /** ネットワークエラーの場合、接続エラーメッセージがスローされること */
  it("ネットワークエラーの場合接続エラーがスローされる", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(request("/api/test")).rejects.toThrow("サーバーに接続できません");
  });

  /** POST リクエストに Cookie の csrf_token が X-CSRF-Token ヘッダーとして付与されること */
  it("POST リクエストに X-CSRF-Token ヘッダーが付与される", async () => {
    Object.defineProperty(document, "cookie", {
      writable: true,
      value: "csrf_token=test-csrf-token",
    });
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);

    await request("/api/test", { method: "POST", body: JSON.stringify({}) });

    const [, options] = fetchMock.mock.calls[0];
    expect((options.headers as Record<string, string>)["X-CSRF-Token"]).toBe("test-csrf-token");
  });

  /** GET リクエストには X-CSRF-Token ヘッダーが付与されないこと */
  it("GET リクエストには X-CSRF-Token ヘッダーが付与されない", async () => {
    const fetchMock = vi.fn().mockResolvedValue(makeResponse(200, {}));
    vi.stubGlobal("fetch", fetchMock);

    await request("/api/test");

    const [, options] = fetchMock.mock.calls[0];
    expect((options.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });
});
