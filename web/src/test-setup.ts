import "@testing-library/jest-dom";
import { afterAll, afterEach, beforeAll } from "vitest";
import { cleanup } from "@testing-library/react";
import { server } from "./test/mswServer";

/** 各テスト後に DOM をクリーンアップ */
afterEach(() => {
  cleanup();
});

/** MSW サーバーのライフサイクル */
beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
