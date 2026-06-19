import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * logger は `import.meta.env.PROD` をモジュール評価時に読むため、環境を切り替えるたびに
 * env をスタブしてからモジュールキャッシュを破棄し、動的 import で再評価する。
 */
async function loadLogger(prod: boolean) {
  vi.stubEnv("PROD", prod);
  vi.resetModules();
  return (await import("./logger")).logger;
}

describe("logger", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("dev では全レベルが対応する console を呼ぶ", async () => {
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {});
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const logger = await loadLogger(false);
    logger.debug("d");
    logger.info("i");
    logger.warn("w");
    logger.error("e");

    expect(debugSpy).toHaveBeenCalledTimes(1);
    expect(infoSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(errorSpy).toHaveBeenCalledTimes(1);
  });

  it("本番では debug / info を抑制し warn / error は出力する", async () => {
    const debugSpy = vi.spyOn(console, "debug").mockImplementation(() => {});
    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => {});
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const logger = await loadLogger(true);
    logger.debug("d");
    logger.info("i");
    logger.warn("w");
    logger.error("e");

    expect(debugSpy).not.toHaveBeenCalled();
    expect(infoSpy).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(errorSpy).toHaveBeenCalledTimes(1);
  });

  it("プレフィックスと追加引数を console へ渡す", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const logger = await loadLogger(false);
    const cause = new Error("boom");
    logger.error("失敗しました", cause);

    expect(errorSpy).toHaveBeenCalledWith("[DevForge]", "失敗しました", cause);
  });
});
